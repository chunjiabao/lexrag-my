"""
B5 - Retrieval configuration controller.

Single entry point that switches between the four retrieval configurations
defined in Section 3.4 / Table 3.5 of the proposal, so the same interface
can be used interactively during development now, and reused as-is by E1
(batch evaluation across all 30 test questions) once the full pipeline
exists. Import `retrieve()` rather than duplicating the method-selection
logic elsewhere.

Wired so far: bm25_only (B1), dense_only (B2).
Not yet wired: hybrid_no_rerank (needs B3 RRF fusion), full (needs B3 + B4
cross-encoder reranker) — calling these raises NotImplementedError with a
message saying what's missing, rather than silently falling back to
something else.
"""

import argparse
import sys

from b1_bm25_index import get_chunk as _get_chunk_bm25
from b1_bm25_index import search_bm25
from b2_dense_index import get_chunk as _get_chunk_dense
from b2_dense_index import search_dense

METHODS = ("bm25_only", "dense_only", "hybrid_no_rerank", "full")

_NOT_YET_IMPLEMENTED = {
    "hybrid_no_rerank": "requires B3 (RRF fusion) — not yet built",
    "full": "requires B3 (RRF fusion) + B4 (cross-encoder reranker) — not yet built",
}


def retrieve(query: str, k: int = 5, method: str = "bm25_only") -> list[dict]:
    """Retrieve top-k statutory chunks for a query using the given method.

    Returns a list of dicts (best match first), each carrying:
    doc_id, score, act_name, section_number, section_heading, full_text,
    is_deleted — one consistent shape regardless of which method produced
    it, so callers (this file's CLI, E1's batch runner, later C1's prompt
    assembly) never need to branch on `method`.
    """
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")
    if method in _NOT_YET_IMPLEMENTED:
        raise NotImplementedError(f"{method}: {_NOT_YET_IMPLEMENTED[method]}")

    if method == "bm25_only":
        hits = search_bm25(query, k=k)
        get_chunk = _get_chunk_bm25
    else:  # dense_only
        hits = search_dense(query, k=k)
        get_chunk = _get_chunk_dense

    return [{**get_chunk(doc_id), "score": score} for doc_id, score in hits]


def _print_results(label: str, results: list[dict]) -> None:
    print(f"\n[{label}]")
    for i, r in enumerate(results, 1):
        preview = r["full_text"][:80].replace("\n", " ")
        print(f"{i}. [{r['score']:6.3f}] {r['doc_id']}  ({r['section_heading']})  {preview}")


if __name__ == "__main__":
    # Windows console defaults to cp1252, which can't print some characters
    # (e.g. en-space U+2002) left over in the PDF-extracted statutory text.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="B5 retrieval configuration controller")
    parser.add_argument("query", help="plain-language legal question")
    parser.add_argument("-k", type=int, default=5, help="top-k chunks to retrieve")
    parser.add_argument(
        "--method",
        choices=METHODS + ("both",),
        default="bm25_only",
        help="'both' is a dev-only side-by-side view, not one of the 4 proposal configs",
    )
    args = parser.parse_args()

    print(f"Query: {args.query}")
    if args.method == "both":
        _print_results("bm25_only", retrieve(args.query, args.k, "bm25_only"))
        _print_results("dense_only", retrieve(args.query, args.k, "dense_only"))
    else:
        _print_results(args.method, retrieve(args.query, args.k, args.method))
