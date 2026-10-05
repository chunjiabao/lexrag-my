import anthropic
from dotenv import load_dotenv
from c0_token_usage import record_usage
from c1_prompt_design import build_prompt

load_dotenv()

client = anthropic.Anthropic()

ANSWER_TOOL = {
    "name": "record_answer",
    "description": "Record the answer as a list of single-fact sentences, each with one cited section and a supporting quote.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "sentences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "One plain-language sentence stating a single fact."},
                        "cited_doc_id": {"type": "string", "description": "doc_id of the one section this sentence relies on, e.g. Act599#42"},
                        "quote": {"type": "string", "description": "Words copied exactly from the cited section that support the sentence."},
                        "heading": {"type": "string", "description": "Short heading of the group this sentence belongs to, or empty for the opening sentence."},
                        "label": {"type": "string", "description": "Short topic name shown before the sentence, or empty for the opening sentence."},
                    },
                    "required": ["text", "cited_doc_id", "quote", "heading", "label"],
                    "additionalProperties": False,
                },
            },
            "not_covered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short topic phrases from the question that the provided sections do not address.",
            },
        },
        "required": ["sentences", "not_covered"],
        "additionalProperties": False,
    },
}


def check_schema(response):
    if response.stop_reason == "max_tokens":
        return None
    # Pull out the answer from the record_answer tool call; the strict schema guarantees its fields and types
    result = next(block.input for block in response.content if block.type == "tool_use")
    return result


def generate(query, context, config, feedback=None):
    system_prompt, user_message = build_prompt(query, context, feedback)

    response = client.messages.create(
        model=config["model"],
        max_tokens=config["generation_max_tokens"],
        system=system_prompt,
        tools=[ANSWER_TOOL],
        tool_choice={"type": "tool", "name": "record_answer"},
        messages=[{"role": "user", "content": user_message}],
        extra_body={"temperature": config["generation_temperature"]},
    )
    record_usage(response, "generation")

   
    result = check_schema(response)
    if result is None:
        return {"status": "insufficient_info", "sentences": [], "not_covered": []}

    if not result["sentences"]:
        return {"status": "insufficient_info", "sentences": [], "not_covered": result["not_covered"]}
    
    return {"status": "generated", "sentences": result["sentences"], "not_covered": result["not_covered"]}
