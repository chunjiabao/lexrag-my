import pickle
import re
from pathlib import Path
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from a5_load_chunks import load_all_chunks

INDEX_DIR = Path("dataset/indexes/bm25")
INDEX_PATH = INDEX_DIR / "bm25_index.pkl"

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text):
    tokens = TOKEN_PATTERN.findall(text.lower())
    # Remove English stop words from the token list
    return [t for t in tokens if t not in ENGLISH_STOP_WORDS]


def build_index(force=False):
    if INDEX_PATH.exists() and not force:
        # Load the index and corpus from the pickle file
        with open(INDEX_PATH, "rb") as f:
            return pickle.load(f)

    corpus = load_all_chunks()

    # Tokenize the full_text of each chunk and build the BM25 retriever
    tokenized_corpus = [tokenize(c["full_text"]) for c in corpus]
    retriever = BM25Okapi(tokenized_corpus)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    # Save the retriever and corpus to a pickle file for future use
    with open(INDEX_PATH, "wb") as f:
        pickle.dump((retriever, corpus), f)
    print(f"Saved index to {INDEX_PATH}")

    return retriever, corpus

retriever, corpus = build_index()


def search_bm25(query, k):
    # Search the BM25 index for the top k results matching the query.
    scores = retriever.get_scores(tokenize(query))
    top_k = scores.argsort()[::-1][:k]
    # Return a list of tuples containing the doc_id and score for the top k results.
    return [(corpus[i]["doc_id"], float(scores[i])) for i in top_k]


def get_chunk(doc_id):
    # Retrieve a chunk from the corpus by its doc_id.
    return next(c for c in corpus if c["doc_id"] == doc_id)
