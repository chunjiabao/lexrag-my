from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from a5_load_chunks import load_all_chunks

INDEX_DIR = Path("dataset") / "indexes" / "chroma"

# Chroma collection name for the statutory sections
COLLECTION_NAME = "statutes"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

# BGE's query special instruction for retrieval
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

model = SentenceTransformer(MODEL_NAME)
# Create a persistent ChromaDB client
client = chromadb.PersistentClient(path=str(INDEX_DIR))

def build_index():
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    corpus = load_all_chunks()

    if collection.count() == len(corpus):
        return collection, corpus

    ids = [c["doc_id"] for c in corpus]
    documents = [c["full_text"] for c in corpus]
    embeddings = model.encode(documents, normalize_embeddings=True).tolist()

    # Add the data to the collection in batches 
    batch_size = 256
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(ids=ids[i:end], documents=documents[i:end], embeddings=embeddings[i:end])
    return collection, corpus


collection, corpus = build_index()

# Dense retrieval
def search_dense(query, k):
    query_embedding = model.encode(
        [QUERY_PREFIX + query], normalize_embeddings=True
    ).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=k)

    # Convert distance to similarity score (1 - distance)
    return [
        (doc_id, 1.0 - dist)
        for doc_id, dist in zip(results["ids"][0], results["distances"][0])
    ]
