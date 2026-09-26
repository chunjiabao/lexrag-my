from b1_bm25_only import search_bm25
from b2_dense_only import search_dense

RRF_K = 60


def fuse(ranked_lists, k=10):
    # Combine ranked lists by rank position only, ignoring each retriever's own score scale
    scores = {}
    for ranked_list in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)

    fused = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return fused[:k]


def search_hybrid(query, k=10, retriever_k=20):
    bm25_hits = search_bm25(query, k=retriever_k)
    dense_hits = search_dense(query, k=retriever_k)
    return fuse([bm25_hits, dense_hits], k=k)
