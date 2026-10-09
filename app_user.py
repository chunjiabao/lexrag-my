# User mode: ask one question at a time and get a verified answer with its sources.
# Run from the project root with: streamlit run app_user.py
# app_dev.py reuses run() from here and plugs in its developer features.

import html
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

DISCLAIMER = (
    "LexRAG-MY explains what the Employment Act 1955, the Consumer Protection Act 1999 and the "
    "Personal Data Protection Act 2010 state. It provides legal information, not legal advice, "
    "and does not consider your personal situation. Consult a lawyer for advice on your case."
)

# Settings start from main.py's CONFIG
from main import CONFIG as DEFAULTS, METHOD

# One highlight colour per answer marker, repeating after six
COLORS = ["#fff3a3","#c8f7c5", "#cfe3ff", "#ffd6e7", "#ffe0b3", "#e3d4ff"]


@st.cache_resource(show_spinner="Loading the indexes and models (Stage 0: first run only)...")
def load_pipeline():
    # Importing the scripts loads the indexes and models, so this runs once per server process
    start = time.perf_counter()
    import c5_verify
    return time.perf_counter() - start


def highlight(text, quotes):
    from c4_quote_match import locate_quote

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


def sources_panel(result):
    from b1_bm25_only import get_chunk

    # Each cited section once, with every quoted passage from it highlighted
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


def run(controls=None, answer=None, answer_footer=None, after_answer=None):
    # User mode passes nothing. app_dev.py passes all four to add its developer features:
    #   controls() -> (method, settings): sidebar controls, replacing main.py's METHOD and CONFIG
    #   answer(query, method, settings) -> (result, timings): runs the pipeline with live progress, replacing the spinner
    #   answer_footer(result, settings): drawn right under the answer text
    #   after_answer(result, timings, settings): drawn under the whole reply
    # Everything Streamlit draws is inside this function, so it redraws on every rerun even when imported
    st.set_page_config(page_title="LexRAG-MY")
    load_pipeline()

    from c5_verify import answer_query, format_answer

    st.title("LexRAG-MY")
    st.caption("Ask a question about Malaysian employment, consumer protection or personal data law.")
    st.info(DISCLAIMER)

    if controls:
        method, settings = controls()
    else:
        method, settings = METHOD, DEFAULTS

    query = st.chat_input("e.g. How much annual leave do I get after three years?")

    # One question at a time: no conversation history is kept
    if query:
        with st.chat_message("user"):
            st.write(query)

        with st.chat_message("assistant"):
            if answer:
                result, timings = answer(query, method, settings)
            else:
                with st.spinner("Finding the answer..."):
                    result = answer_query(query, method, settings)
                timings = []

            st.markdown(format_answer(result))
            if answer_footer:
                answer_footer(result, settings)

            if result["sentences"]:
                sources_panel(result)

        if after_answer:
            after_answer(result, timings, settings)


if __name__ == "__main__":
    run()
