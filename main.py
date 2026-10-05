# Run one question through the full pipeline and print the answer, sources and check results.
# Run from the project root with: python main.py
# CONFIG is also the default settings for app.py.

import sys
from pathlib import Path

QUERY = "What is annual leave entitlement and how do I file a divorce?"
METHOD = "hybrid_no_rerank"     # bm25_only | dense_only | hybrid_no_rerank | full (full is the proposed system)

CONFIG = {
    # Retrieval
    "top_k": 5,                 # sections passed to the model as context
    "retriever_k": 20,          # hybrid_no_rerank, full: how deep BM25 and dense each search before fusion
    "candidate_k": 20,          # full only: fused results sent to the reranker; lower is faster but may reduce accuracy
    "max_expansion": 3,         # max cross-referenced sections added to the context
    "rrf_k": 60,                # hybrid_no_rerank, full: rank fusion constant; higher flattens the gap between ranks

    # Generation
    "model": "claude-haiku-4-5-20251001",   # Claude Haiku 4.5, used for both generation and the judge
    "input_price": 1.00,                    # USD per million input tokens (Haiku 4.5)
    "output_price": 5.00,                   # USD per million output tokens (Haiku 4.5)
    "generation_max_tokens": 4096,          # output limit; a cut-off answer fails the schema check
    "generation_temperature": 0,            # 0 gives the same answer for the same input

    # Verification
    "fuzzy_threshold": 90,      # minimum similarity (0-100) for a quote that is not an exact match
    "judge_max_tokens": 512,
    "judge_temperature": 0,
}


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
    from b1_bm25_only import get_chunk
    from c0_token_usage import usage_cost
    from c5_verify import answer_query, format_answer

    result = answer_query(QUERY, METHOD, CONFIG)

    print(f"\nQuery: {QUERY}")
    print(f"Method: {METHOD}")
    print("\nRetrieved:")
    for doc_id, score in result["retrieved"]:
        print(f"  {score:.4f} {doc_id} {get_chunk(doc_id)['section_heading']}")
    print("Expanded:")
    for doc_id, referred_by in result["expanded"]:
        print(f"  {doc_id} {get_chunk(doc_id)['section_heading']} (referred by {referred_by})")

    usage = result["usage"]
    print(f"\nStatus: {result['status']}")
    print(f"Tokens: {usage['input_tokens']:,} input / {usage['output_tokens']:,} output "
          f"(${usage_cost(usage, CONFIG):.4f})\n")
    print(format_answer(result))

    # Source panel: each cited section with its quoted passage
    if result["sentences"]:
        print("\nSources:")
        for i, s in enumerate(result["sentences"], start=1):
            chunk = get_chunk(s["cited_doc_id"])
            print(f"  [{i}] {s['cited_doc_id']} {chunk['section_heading']}")
            print(f"      \"{s['quote']}\"")

    # Check results for every attempt
    for attempt in result["attempts"]:
        print(f"\nAttempt ({'stricter' if attempt['strict'] else 'initial'} prompt): {attempt['status']}")
        for i, row in enumerate(attempt["checks"], start=1):
            print(f"  {i}. [{row['provenance']} / {row['quote_match']} / {row['support']}] {row['sentence']['text']}")
            if row["reason"]:
                print(f"      Reason: {row['reason']}")
