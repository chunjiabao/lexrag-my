def check_provenance(sentence, retrieved_ids, expanded_ids):
    doc_id = sentence["cited_doc_id"]
    if doc_id in retrieved_ids:
        return "retrieved"
    if doc_id in expanded_ids:
        return "expanded"
    return "not_provided"
