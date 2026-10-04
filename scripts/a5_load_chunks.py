#Combine validated chunks from all Acts into one corpus for indexing and retrieval.

import json
import os

CHUNKS_DIR = os.path.join("dataset", "chunks_validated")

ACTS = [
    {"code": "Act265", "file": "Act265_chunks.json"},
    {"code": "Act599", "file": "Act599_chunks.json"},
    {"code": "Act709", "file": "Act709_chunks.json"},
]



def load_all_chunks():
    corpus = []
    for act in ACTS:
        #generate file path for each act's chunk file and load the chunks
        path = os.path.join(CHUNKS_DIR, act['file'])
        with open(path, encoding="utf-8") as f:
            chunks = json.load(f)
        #generate a unique doc_id for each chunk and add it to the corpus
        for chunk in chunks:
            doc_id = f"{act['code']}#{chunk['section_number']}"
            corpus.append({"doc_id": doc_id, **chunk})
    return corpus


if __name__ == "__main__":
    corpus = load_all_chunks()
    print(f"Loaded {len(corpus)} chunks across {len(ACTS)} Acts")
    deleted = sum(1 for c in corpus if c["is_deleted"])
    print(f"  is_deleted: {deleted}")
