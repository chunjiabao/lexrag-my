# User mode: ask one question at a time and get a verified answer with its sources.
# Developer mode: also change the pipeline settings and inspect the process stats and raw JSON output.
# Run from the project root with: streamlit run app.py

import html
import json
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

st.set_page_config(page_title="LexRAG-MY")

METHODS = ["full", "hybrid_no_rerank", "dense_only", "bm25_only"]

DISCLAIMER = (
    "LexRAG-MY explains what the Employment Act 1955, the Consumer Protection Act 1999 and the "
    "Personal Data Protection Act 2010 state. It provides legal information, not legal advice, "
    "and does not consider your personal situation. Consult a lawyer for advice on your case."
)

# Developer settings start from main.py's CONFIG
from main import CONFIG as DEFAULTS, METHOD


@st.cache_resource(show_spinner="Loading the indexes and models (first run only)...")
def load_pipeline():
    # Importing the scripts loads the indexes and models, so this runs once per server process
    start = time.perf_counter()
    import c5_verify
    return time.perf_counter() - start


load_time = load_pipeline()

from b1_bm25_only import get_chunk
from c4_quote_match import locate_quote
from c2_generate import PRICES, usage_cost
from c5_verify import answer_query, format_answer


# One highlight colour per answer marker, repeating after six
COLORS = ["#fff3a3","#c8f7c5", "#cfe3ff", "#ffd6e7", "#ffe0b3", "#e3d4ff"]


def highlight(text, quotes):
    # Mark each quoted passage inside the full section text in its own colour, labelled with its marker number
    spans = sorted((*locate_quote(quote, text)[1:], n) for n, quote in quotes)
    parts = []
    pos = 0
    for start, end, n in spans:
        # Overlapping quotes: only mark the part not already marked
        start = max(start, pos)
        if start >= end:
            continue
        color = COLORS[(n - 1) % len(COLORS)]
        parts.append(html.escape(text[pos:start]))
        parts.append(f'<sup><b>[{n}]</b></sup><mark style="background-color: {color}; color: black">'
                     f'{html.escape(text[start:end])}</mark>')
        pos = end
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def settings_form():
    # Saved settings last for this browser session and are used in both modes
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
        model = st.selectbox("Model (generation and judge)", list(PRICES), index=list(PRICES).index(s["model"]))
        generation_max_tokens = st.number_input("Max tokens", 256, 16000, s["generation_max_tokens"], step=256)
        generation_temperature = st.slider("Temperature", 0.0, 1.0, float(s["generation_temperature"]), 0.1)

        st.markdown("**Verification**")
        min_quote_words = st.number_input("MIN_QUOTE_WORDS: shortest accepted quote", 1, 30, s["min_quote_words"],
                                          help="The stricter prompt's text still says 'at least five words'.")
        fuzzy_threshold = st.slider("FUZZY_THRESHOLD: quote match similarity", 0, 100, s["fuzzy_threshold"])
        judge_max_tokens = st.number_input("Judge max tokens", 128, 4096, s["judge_max_tokens"], step=128)
        judge_temperature = st.slider("Judge temperature", 0.0, 1.0, float(s["judge_temperature"]), 0.1)

        saved = st.form_submit_button("Save", type="primary")

    if saved:
        st.session_state.settings = {
            "top_k": top_k, "retriever_k": retriever_k, "candidate_k": candidate_k, "max_expansion": max_expansion,
            "rrf_k": rrf_k, "model": model, "generation_max_tokens": generation_max_tokens,
            "generation_temperature": generation_temperature, "min_quote_words": min_quote_words,
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
    st.divider()
    st.subheader("Developer")
    stats_tab, json_tab = st.tabs(["Process stats", "JSON"])

    with stats_tab:
        st.markdown("**Timing**")
        st.dataframe([{"Phase": name, "Seconds": round(seconds, 3)} for name, seconds in timings], hide_index=True)

        st.markdown("**Tokens**")
        usage = result["usage"]
        rows = []
        for label, counts in [("Generation", usage["generation"]), ("Judge", usage["judge"]), ("Total", usage)]:
            rows.append({"Calls": label, "Input": counts["input_tokens"], "Output": counts["output_tokens"],
                         "Cost (USD)": round(usage_cost(counts, settings["model"]), 5)})
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


if "settings" not in st.session_state:
    st.session_state.settings = dict(DEFAULTS)

st.title("LexRAG-MY")
st.caption("Ask a question about Malaysian employment, consumer protection or personal data law.")
st.info(DISCLAIMER)

with st.sidebar:
    mode = st.radio("Mode", ["User", "Developer"], horizontal=True)
    method = st.selectbox("Retrieval method", METHODS, index=METHODS.index(METHOD))
    st.caption("full is the proposed system. The others are the baselines used in evaluation.")
    if mode == "Developer":
        settings_form()
    elif st.session_state.settings != DEFAULTS:
        st.caption("Custom developer settings are active.")
    st.caption(f"Indexes and models loaded in {load_time:.1f}s (once per server start).")

query = st.chat_input("e.g. How much annual leave do I get after three years?")

# One question at a time: no conversation history is kept
if query:
    settings = st.session_state.settings

    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
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

            result = answer_query(query, method, settings, on_phase=on_phase)
            # Close the last phase
            on_phase(None)
            status.update(label=f"Done in {time.perf_counter() - start:.1f}s", state="complete", expanded=False)

        st.markdown(format_answer(result))
        tokens = result["usage"]
        st.caption(f"Status: {result['status']} · Tokens: {tokens['input_tokens']:,} input / "
                   f"{tokens['output_tokens']:,} output · Cost: ${usage_cost(tokens, settings["model"]):.4f}")

        # Source panel: each cited section once, with every quoted passage from it highlighted
        if result["sentences"]:
            st.markdown("**Sources**")
            groups = {}
            for i, s in enumerate(result["sentences"], start=1):
                groups.setdefault(s["cited_doc_id"], []).append((i, s["quote"]))
            for doc_id, quotes in groups.items():
                chunk = get_chunk(doc_id)
                numbers = ", ".join(str(n) for n, quote in quotes)
                with st.expander(f"[{numbers}] {chunk['act_name']}, section {chunk['section_number']}: {chunk['section_heading']}"):
                    st.markdown(f'<div style="white-space: pre-wrap">{highlight(chunk["full_text"], quotes)}</div>',
                                unsafe_allow_html=True)

    if mode == "Developer":
        developer_panel(result, timings, settings)
