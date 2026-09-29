import anthropic
from dotenv import load_dotenv
from c1_prompt_design import SYSTEM_PROMPT, SYSTEM_PROMPT_STRICT, build_user_message

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"

client = anthropic.Anthropic()

ANSWER_TOOL = {
    "name": "record_answer",
    "description": "Record the generated answer and its per claim citations.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "Plain language answer to the user's question."},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_text": {"type": "string"},
                        "quote": {"type": "string", "description": "Exact words copied from the cited section that state this fact."},
                        "cited_doc_id": {"type": "string", "description": "doc_id of the section this claim is based on, e.g. Act599#42"},
                    },
                    "required": ["claim_text", "quote", "cited_doc_id"],
                    "additionalProperties": False,
                },
            },
            "insufficient_info": {"type": "boolean", "description": "True only if the retrieved sections answer none of the question."},
        },
        "required": ["answer", "claims", "insufficient_info"],
        "additionalProperties": False,
    },
}


def call(system_prompt, query, chunks):
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        tools=[ANSWER_TOOL],
        tool_choice={"type": "tool", "name": "record_answer"},
        messages=[{"role": "user", "content": build_user_message(query, chunks)}],
    )
    # Pull out the answer from the record_answer tool call
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_answer":
            return block.input
    return None

# Validate the structure of the generated result
def valid(result):
    if not isinstance(result, dict):
        return False
    if not isinstance(result.get("answer"), str) or not isinstance(result.get("claims"), list):
        return False
    for claim in result["claims"]:
        if not isinstance(claim, dict):
            return False
        if not isinstance(claim.get("claim_text"), str) or not isinstance(claim.get("cited_doc_id"), str):
            return False
        if not isinstance(claim.get("quote"), str):
            return False
    return True


def generate(query, chunks, strict=False):
    if strict:
        system_prompt = SYSTEM_PROMPT_STRICT
    else:
        system_prompt = SYSTEM_PROMPT

    result = call(system_prompt, query, chunks)

    if valid(result):
        return result
    
    result = call(system_prompt + "\n\nYou must call record_answer with valid arguments matching its schema exactly.", query, chunks)
    if valid(result):
        return result

    return {"answer": "Unable to generate a verified response.", "claims": [], "insufficient_info": True}


if __name__ == "__main__":
    from b1_bm25_only import get_chunk
    from b5_retrieval_controller import retrieve, QUERY, METHOD, TOP_K, RETRIEVER_K, CANDIDATE_K

    results = retrieve(QUERY, k=TOP_K, method=METHOD, retriever_k=RETRIEVER_K, candidate_k=CANDIDATE_K)
    chunks = [get_chunk(doc_id) for doc_id, score in results]

    output = generate(QUERY, chunks)
    print(f"\nQuery: {QUERY}\n")
    print(f"Retrieval method: {METHOD}\n")
    print("Answer:", output["answer"])
    print("Insufficient info:", output["insufficient_info"])
    print("Claims:")
    # Group claims by cited_doc_id for easier reading
    grouped = {}
    for claim in output["claims"]:
        grouped.setdefault(claim["cited_doc_id"], []).append(claim)
    for doc_id, claims in grouped.items():
        print(f"  [{doc_id}]")
        for claim in claims:
            print(f"    - {claim['claim_text']}")
            print(f"        Quote: \"{claim['quote']}\"")
