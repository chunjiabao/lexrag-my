import time
from b1_bm25_only import search_bm25, get_chunk
from b2_dense_only import search_dense
from b3_hybrid_no_rerank import search_hybrid
from b4_full import search_full

QUERY = "What is annual leave entitlement and how do I file a divorce?"
METHOD = "bm25_only"        # bm25_only | dense_only | hybrid_no_rerank | full
TOP_K = 5               # how many results to return to the user
RETRIEVER_K = 20        # hybrid_no_rerank, full: how deep BM25/dense each search before fusion
CANDIDATE_K = 20        # full only: how many fused results go into the reranker


def retrieve(query, k, method, retriever_k, candidate_k):
    if method == "bm25_only":
        return search_bm25(query, k=k)
    elif method == "dense_only":
        return search_dense(query, k=k)
    elif method == "hybrid_no_rerank":
        return search_hybrid(query, k=k, retriever_k=retriever_k)
    elif method == "full":
        return search_full(query, k=k, retriever_k=retriever_k, candidate_k=candidate_k)
    else:
        return f"Invalid method: {method}"


if __name__ == "__main__":

    print(f"\nQuery: {QUERY}")
    print(f"Method: {METHOD}\n")
    start = time.perf_counter()
    results = retrieve(QUERY, k=TOP_K, method=METHOD, retriever_k=RETRIEVER_K, candidate_k=CANDIDATE_K)
    elapsed = time.perf_counter() - start

    for doc_id, score in results:
        print(f"{score:.4f}", doc_id, get_chunk(doc_id)["section_heading"])

    print(f"\nTime taken: {elapsed:.3f}s")
