from b1_bm25_only import search_bm25, get_chunk
from b2_dense_only import search_dense
from b3_hybrid_no_rerank import search_hybrid
from b4_full import search_full


def retrieve(query, method, config):
    k = config["top_k"]
    if method == "bm25_only":
        return search_bm25(query, k=k)
    elif method == "dense_only":
        return search_dense(query, k=k)
    elif method == "hybrid_no_rerank":
        return search_hybrid(query, k=k, retriever_k=config["retriever_k"], rrf_k=config["rrf_k"])
    elif method == "full":
        return search_full(query, k=k, retriever_k=config["retriever_k"], candidate_k=config["candidate_k"],
                           rrf_k=config["rrf_k"])
    else:
        print(f"Invalid method: {method}")
        return []


def expand(results, max_expansion):
    # Expand the top-k results by following cross-references in the corpus
    top_ids = [doc_id for doc_id, score in results]
    expanded = []
    for doc_id in top_ids:
        for ref_id in get_chunk(doc_id)["references"]:
            if len(expanded) == max_expansion:
                return expanded
            # Skip sections already in the top-k or already added
            if ref_id in top_ids or ref_id in [e[0] for e in expanded]:
                continue
            expanded.append((ref_id, doc_id))
    return expanded

