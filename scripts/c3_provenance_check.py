from a5_load_chunks import load_all_chunks

# Every section identifier in the three Acts, used to tell a real but unprovided section from an invented one
ALL_DOC_IDS = {c["doc_id"] for c in load_all_chunks()}


# The cited section must be one of the sections in the context set given to the generator
def check_provenance(sentence, retrieved_ids, expanded_ids):
    doc_id = sentence["cited_doc_id"]
    if doc_id in retrieved_ids:
        return "retrieved"
    if doc_id in expanded_ids:
        return "expanded"
    # Failed: the section exists in the Acts but was not provided, or it does not exist at all
    if doc_id in ALL_DOC_IDS:
        return "not_retrieved"
    return "nonexistent"
