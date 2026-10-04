from sentence_transformers import CrossEncoder
from b1_bm25_only import get_chunk
from b3_hybrid_no_rerank import search_hybrid

MODEL_NAME = "BAAI/bge-reranker-base"

model = CrossEncoder(MODEL_NAME)


def rerank(query, candidate_ids, k):
    pairs = [[query, get_chunk(doc_id)["full_text"]] for doc_id in candidate_ids]
    scores = model.predict(pairs)

    # Sort the candidates by the cross-encoder's relevance score
    reranked = sorted(zip(candidate_ids, scores), key=lambda item: item[1], reverse=True)
    return reranked[:k]


def search_full(query, k, retriever_k, candidate_k, rrf_k):
    candidates = search_hybrid(query, k=candidate_k, retriever_k=retriever_k, rrf_k=rrf_k)
    candidate_ids = [doc_id for doc_id, score in candidates]
    return rerank(query, candidate_ids, k=k)
