import argparse
import pickle
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from load_chunks import load_all_chunks

INDEX_DIR = Path("dataset/indexes/bm25")
INDEX_PATH = INDEX_DIR / "bm25_index.pkl"

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, drop English stopwords."""
    tokens = TOKEN_PATTERN.findall(text.lower())
    return [t for t in tokens if t not in ENGLISH_STOP_WORDS]


def build_index(force: bool = False) -> tuple[BM25Okapi, list[dict]]:
    """Build (Stage 0, one-time) or load-from-cache the BM25 index."""
    if INDEX_PATH.exists() and not force:
        print(f"Loading cached BM25 index from {INDEX_PATH}")
        with open(INDEX_PATH, "rb") as f:
            return pickle.load(f)

    corpus = load_all_chunks()
    print(f"Indexing {len(corpus)} statutory sections with BM25...")

    tokenized_corpus = [tokenize(c["full_text"]) for c in corpus]
    retriever = BM25Okapi(tokenized_corpus)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump((retriever, corpus), f)
    print(f"Saved index to {INDEX_PATH}")

    return retriever, corpus


_retriever, _corpus = build_index()


def search_bm25(query: str, k: int = 10) -> list[tuple[str, float]]:
    """Return the top-k (doc_id, score) pairs for a plain-language query."""
    scores = _retriever.get_scores(tokenize(query))
    top_k = scores.argsort()[::-1][:k]
    return [(_corpus[i]["doc_id"], float(scores[i])) for i in top_k]


def get_chunk(doc_id: str) -> dict:
    """Look up the full chunk metadata for a doc_id."""
    return next(c for c in _corpus if c["doc_id"] == doc_id)


if __name__ == "__main__":
    # Windows console defaults to cp1252, which can't print some characters
    # (e.g. en-space U+2002) left over in the PDF-extracted statutory text.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="force re-index")
    args = parser.parse_args()
    if args.rebuild:
        _retriever, _corpus = build_index(force=True)

    query = "Can I get any refund for receiving a defective item?"
    print(f"\nQuery: {query}\n")
    for i, (doc_id, score) in enumerate(search_bm25(query, k=5), 1):
        chunk = get_chunk(doc_id)
        preview = chunk["full_text"][:80].replace("\n", " ")
        print(f"{i}. [{score:6.2f}] {doc_id}  ({chunk['section_heading']})  {preview}")
