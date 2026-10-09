# Developer mode: the user mode page, plus the pipeline settings and the process stats and raw JSON output.
# A sidebar switch flips between User (the app_user.py page as is) and Developer.
# Run from the project root with: streamlit run app_dev.py

import json
import time
from contextlib import contextmanager

import streamlit as st

from app_user import DEFAULTS, METHOD, load_pipeline, run

METHODS = ["full", "hybrid_no_rerank", "dense_only", "bm25_only"]

GENERATION_FAULTS = ["None", "Cut off", "No sentences"]
CHECK_FAULTS = ["None", "Provenance", "Quote match", "Support"]
FAULT_ATTEMPTS = ["First attempt only", "Retry only", "Both attempts"]
FAULT_SENTENCES = ["All sentences", "Sentence 1 only"]


def controls():
    # Sidebar: retrieval method, pipeline settings, fault injection and load time.
    # Returns the method and settings to run with
    if "settings" not in st.session_state:
        st.session_state.settings = dict(DEFAULTS)
    with st.sidebar:
        method = st.selectbox("Retrieval method", METHODS, index=METHODS.index(METHOD))
        st.caption("full is the proposed system. The others are the baselines used in evaluation.")
        settings_form()
        st.session_state.faults = fault_form()
        # load_pipeline is cached, so this returns the time from the first load
        st.caption(f"Indexes and models loaded in {load_pipeline():.1f}s (once per server start).")
    return method, st.session_state.settings


def fault_form():
    # Force a pipeline step to fail. A forced step skips the API call it replaces; steps not forced still call it.
    # Options only appear when they have an effect; hidden ones keep their first value
    faults = {"generation": "None", "check": "None", "attempts": FAULT_ATTEMPTS[0], "sentences": FAULT_SENTENCES[0]}
    st.divider()
    if not st.toggle("Fault injection"):
        st.caption("Off: the pipeline runs exactly like User mode.")
        return faults

    faults["generation"] = st.selectbox("Generation fault", GENERATION_FAULTS,
                                        help="Cut off: as if max_tokens was hit. No sentences: the question is not "
                                             "covered. Either one ends the run as insufficient_info, with no retry.")
    faults["check"] = st.selectbox("Check fault", CHECK_FAULTS, help="The check fails, so the later checks are skipped.")
    if faults["generation"] != "None" or faults["check"] != "None":
        faults["attempts"] = st.selectbox("Apply to attempt", FAULT_ATTEMPTS)
    if faults["check"] != "None":
        faults["sentences"] = st.selectbox("Check fault applies to", FAULT_SENTENCES)
    return faults


def describe_faults(faults):
    # One line per active fault, for the developer panel and the JSON output
    lines = []
    if faults["generation"] != "None":
        lines.append(f"Generation: {faults['generation']} ({faults['attempts']})")
    if faults["check"] != "None":
        lines.append(f"Check: {faults['check']} ({faults['attempts']}, {faults['sentences']})")
    return lines


@contextmanager
def faults_injected(faults):
    # Swap c5_verify's step functions for versions that fail on purpose, and always put the real ones back.
    # This affects the whole server process while the run lasts, so use it on a local server only
    import c5_verify

    if not describe_faults(faults):
        yield
        return

    names = ["generate", "check_provenance", "locate_quote", "check_support"]
    real = {name: getattr(c5_verify, name) for name in names}
    # attempt: 1 for the first generation, 2 for the retry; sentence: which sentence verify() is checking
    state = {"attempt": 0, "sentence": 0}

    def attempt_applies():
        if faults["attempts"] == "Both attempts":
            return True
        if faults["attempts"] == "First attempt only":
            return state["attempt"] == 1
        return state["attempt"] == 2

    def check_applies(check):
        return (faults["check"] == check and attempt_applies()
                and (faults["sentences"] == "All sentences" or state["sentence"] == 1))

    def generate(query, context, config, feedback=None):
        state["attempt"] += 1
        state["sentence"] = 0
        if faults["generation"] != "None" and attempt_applies():
            not_covered = [query] if faults["generation"] == "No sentences" else []
            return {"status": "insufficient_info", "sentences": [], "not_covered": not_covered}
        return real["generate"](query, context, config, feedback=feedback)

    def check_provenance(sentence, retrieved_ids, expanded_ids):
        # verify() calls this first for every sentence, so it also counts the sentences
        state["sentence"] += 1
        if check_applies("Provenance"):
            return "not_provided"
        return real["check_provenance"](sentence, retrieved_ids, expanded_ids)

    def locate_quote(quote, text):
        if check_applies("Quote match"):
            return 0, 0, 0
        return real["locate_quote"](quote, text)

    def check_support(sentence, chunk, start, end, config):
        if check_applies("Support"):
            return "not_supported", "[forced] dev fault injection"
        return real["check_support"](sentence, chunk, start, end, config)

    fakes = {"generate": generate, "check_provenance": check_provenance,
             "locate_quote": locate_quote, "check_support": check_support}
    for name in names:
        setattr(c5_verify, name, fakes[name])
    try:
        yield
    finally:
        for name in names:
            setattr(c5_verify, name, real[name])


def answer_with_progress(query, method, settings):
    from c5_verify import answer_query

    # Show each pipeline phase as it runs, with the time it took
    timings = []
    with st.status("Starting...", expanded=True) as status:
        start = time.perf_counter()
        current = {"name": None, "start": start}

        def on_phase(name):
            now = time.perf_counter()
            if current["name"]:
                st.write(f"✓ {current['name']}: {now - current['start']:.2f}s")
                timings.append((current["name"], now - current["start"]))
            current["name"], current["start"] = name, now
            if name:
                status.update(label=f"{name}...")

        faults = st.session_state.faults
        with faults_injected(faults):
            result = answer_query(query, method, settings, on_phase=on_phase)
        result["faults"] = describe_faults(faults)
        # Close the last phase
        on_phase(None)
        status.update(label=f"Done in {time.perf_counter() - start:.1f}s", state="complete", expanded=False)
    return result, timings


def status_line(result, settings):
    from c0_token_usage import usage_cost

    tokens = result["usage"]
    st.caption(f"Status: {result['status']} · Tokens: {tokens['input_tokens']:,} input / "
               f"{tokens['output_tokens']:,} output · Cost: ${usage_cost(tokens, settings):.4f}")


def settings_form():
    # Saved settings last for this browser session
    s = st.session_state.settings
    with st.form("settings_form"):
        st.markdown("**Retrieval**")
        top_k = st.number_input("TOP_K: sections passed to the model", 1, 20, s["top_k"])
        retriever_k = st.number_input("RETRIEVER_K: BM25/dense depth before fusion", 1, 100, s["retriever_k"],
                                      help="hybrid_no_rerank and full only.")
        candidate_k = st.number_input("CANDIDATE_K: fused results sent to the reranker", 1, 100, s["candidate_k"],
                                      help="full only. Lower is faster but may reduce accuracy.")
        max_expansion = st.number_input("MAX_EXPANSION: cross-referenced sections added", 0, 10, s["max_expansion"])
        rrf_k = st.number_input("RRF_K: rank fusion constant", 1, 200, s["rrf_k"],
                                help="hybrid_no_rerank and full only.")

        st.markdown("**Generation**")
        generation_max_tokens = st.number_input("Max tokens", 256, 16000, s["generation_max_tokens"], step=256)
        generation_temperature = st.slider("Temperature", 0.0, 1.0, float(s["generation_temperature"]), 0.1)

        st.markdown("**Verification**")
        fuzzy_threshold = st.slider("FUZZY_THRESHOLD: quote match similarity", 0, 100, s["fuzzy_threshold"])
        judge_max_tokens = st.number_input("Judge max tokens", 128, 4096, s["judge_max_tokens"], step=128)
        judge_temperature = st.slider("Judge temperature", 0.0, 1.0, float(s["judge_temperature"]), 0.1)

        saved = st.form_submit_button("Save", type="primary")

    if saved:
        # The model and its prices are fixed, so they are kept from the current settings
        st.session_state.settings = {
            **s, "top_k": top_k, "retriever_k": retriever_k, "candidate_k": candidate_k, "max_expansion": max_expansion,
            "rrf_k": rrf_k, "generation_max_tokens": generation_max_tokens,
            "generation_temperature": generation_temperature,
            "fuzzy_threshold": fuzzy_threshold, "judge_max_tokens": judge_max_tokens,
            "judge_temperature": judge_temperature,
        }
        st.success("Settings saved.")
        if candidate_k < top_k:
            st.warning("CANDIDATE_K is below TOP_K, so full returns only CANDIDATE_K sections.")
    if st.button("Reset to defaults"):
        st.session_state.settings = dict(DEFAULTS)
        st.rerun()


def developer_panel(result, timings, settings):
    from b1_bm25_only import get_chunk
    from c0_token_usage import usage_cost

    st.divider()
    st.subheader("Developer")
    if result["faults"]:
        st.warning("Fault injection active: " + "; ".join(result["faults"]))
    stats_tab, json_tab = st.tabs(["Process stats", "JSON"])

    with stats_tab:
        st.markdown("**Timing**")
        st.dataframe([{"Phase": name, "Seconds": round(seconds, 3)} for name, seconds in timings], hide_index=True)

        st.markdown("**Tokens**")
        usage = result["usage"]
        rows = []
        for label, counts in [("Generation", usage["generation"]), ("Judge", usage["judge"]), ("Total", usage)]:
            rows.append({"Calls": label, "Input": counts["input_tokens"], "Output": counts["output_tokens"],
                         "Cost (USD)": round(usage_cost(counts, settings), 5)})
        st.dataframe(rows, hide_index=True)

        st.markdown(f"**Retrieved ({result['method']})**")
        st.dataframe([{"Rank": rank, "doc_id": doc_id, "Score": round(float(score), 4),
                       "Heading": get_chunk(doc_id)["section_heading"]}
                      for rank, (doc_id, score) in enumerate(result["retrieved"], start=1)], hide_index=True)

        if result["expanded"]:
            st.markdown("**Added by cross-reference expansion**")
            st.dataframe([{"doc_id": doc_id, "Referred to by": referred_by,
                           "Heading": get_chunk(doc_id)["section_heading"]}
                          for doc_id, referred_by in result["expanded"]], hide_index=True)

        for attempt in result["attempts"]:
            prompt = "stricter" if attempt["strict"] else "initial"
            st.markdown(f"**Attempt ({prompt} prompt): {attempt['status']}**")
            if attempt["checks"]:
                st.dataframe([{"#": i, "Passed": row["passed"], "Provenance": row["provenance"],
                               "Quote match": row["quote_match"], "Support": row["support"],
                               "Reason": row["reason"], "Sentence": row["sentence"]["text"]}
                              for i, row in enumerate(attempt["checks"], start=1)], hide_index=True)
            if attempt["not_covered"]:
                st.caption("Not covered: " + "; ".join(attempt["not_covered"]))

    with json_tab:
        # Retriever scores can be numpy floats, which json cannot write directly
        data = json.dumps({"settings": settings, "timings": timings, "result": result},
                          indent=2, default=float, ensure_ascii=False)
        st.download_button("Download JSON", data, file_name="lexrag_result.json", mime="application/json",
                           on_click="ignore")
        st.json(data, expanded=2)


# User shows exactly the app_user.py page; Developer adds the developer features to it
with st.sidebar:
    mode = st.radio("Mode", ["User", "Developer"], horizontal=True)

if mode == "Developer":
    run(controls=controls, answer=answer_with_progress, answer_footer=status_line, after_answer=developer_panel)
else:
    run()
