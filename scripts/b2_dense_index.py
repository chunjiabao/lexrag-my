"""
B2 - Dense retrieval index over the validated Malaysian statutory chunks.

Embeds each chunk's full_text once with a local SentenceTransformers model
(Table 3.6 — runs locally, no external API cost) and stores the vectors +
metadata in ChromaDB (Table 3.6), so runtime queries only need to embed the
query text and hit the persisted collection (Stage 0: one-time indexing,
Section 3.2 / Section 3.4.2).

Model: BAAI/bge-small-en-v1.5 — small (~130MB), fast, and from the same BGE
family as the cross-encoder reranker already chosen for B4 (Table 3.6),
which keeps the embedding/reranking story consistent in the report. BGE
models are trained for asymmetric retrieval and expect an instruction
prefix on the QUERY side only, never on passages — see `_QUERY_PREFIX`.
(Swap MODEL_NAME here if you'd rather use a different SentenceTransformers
model; nothing else in this file depends on the choice.)

Reference structure adapted from:
https://github.com/daveebbelaar/ai-cookbook/tree/main/knowledge/hybrid-retrieval
(same shape: embed corpus once -> cache -> search_dense() by similarity),
swapped from OpenAI text-embedding-3-small + numpy onto a local
SentenceTransformers model + ChromaDB, per our approved tech stack.
"""

import argparse
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from load_chunks import load_all_chunks

INDEX_DIR = Path("dataset/indexes/chroma")
COLLECTION_NAME = "statutes"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

# BGE's own convention: prepend this to QUERIES only (not documents) for
# asymmetric retrieval quality. https://huggingface.co/BAAI/bge-small-en-v1.5
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = SentenceTransformer(MODEL_NAME)
_client = chromadb.PersistentClient(path=str(INDEX_DIR))


def build_index(force=False):
    """Build (Stage 0, one-time) or reuse the Chroma collection."""
    if force:
        try:
            _client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = _client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    corpus = load_all_chunks()

    if collection.count() == len(corpus) and not force:
        print(f"Reusing cached Chroma collection ({collection.count()} chunks)")
        return collection

    print(f"Embedding {len(corpus)} statutory sections with {MODEL_NAME}...")

    ids = [c["doc_id"] for c in corpus]
    documents = [c["full_text"] for c in corpus]
    metadatas = [
        {
            "act_name": c["act_name"],
            "section_number": c["section_number"],
            "section_heading": c["section_heading"] or "",
            "is_deleted": c["is_deleted"],
        }
        for c in corpus
    ]

    embeddings = _model.encode(
        documents, normalize_embeddings=True, show_progress_bar=True
    ).tolist()

    # Chroma's add() has a batch-size ceiling; ~470 chunks fits in one call,
    # but batch defensively in case the corpus grows (more Acts added later).
    batch_size = 256
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
        )
    print(f"Saved {collection.count()} embeddings to {INDEX_DIR}")

    return collection


_collection = build_index()
_corpus_by_id = {c["doc_id"]: c for c in load_all_chunks()}


def search_dense(query, k=10):
    """Return the top-k (doc_id, similarity) pairs for a plain-language query."""
    query_embedding = _model.encode(
        [_QUERY_PREFIX + query], normalize_embeddings=True
    ).tolist()
    results = _collection.query(query_embeddings=query_embedding, n_results=k)

    # cosine space: Chroma returns distance = 1 - cosine_similarity
    return [
        (doc_id, 1.0 - dist)
        for doc_id, dist in zip(results["ids"][0], results["distances"][0])
    ]


def get_chunk(doc_id):
    """Look up the full chunk metadata for a doc_id (mirrors b1's get_chunk)."""
    return _corpus_by_id[doc_id]


if __name__ == "__main__":
    # Windows console defaults to cp1252, which can't print some characters
    # (e.g. en-space U+2002) left over in the PDF-extracted statutory text.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="force re-index")
    args = parser.parse_args()
    if args.rebuild:
        _collection = build_index(force=True)

    query = "Can I get any refund for receiving a defective item?"
    print(f"\nQuery: {query}\n")
    for i, (doc_id, score) in enumerate(search_dense(query, k=5), 1):
        result = _collection.get(ids=[doc_id])
        meta = result["metadatas"][0]
        preview = result["documents"][0][:80].replace("\n", " ")
        print(f"{i}. [{score:.3f}] {doc_id}  ({meta['section_heading']})  {preview}")

