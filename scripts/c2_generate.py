import anthropic
from dotenv import load_dotenv
from c1_prompt_design import SYSTEM_PROMPT, SYSTEM_PROMPT_STRICT, build_user_message

load_dotenv()

# USD per million (input, output) tokens for each model that can be selected
PRICES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}

client = anthropic.Anthropic()

def reset_usage():
    # Start a fresh count for a new question; earlier results keep their own dict
    global usage
    usage = {"input_tokens": 0, "output_tokens": 0,
             "generation": {"input_tokens": 0, "output_tokens": 0},
             "judge": {"input_tokens": 0, "output_tokens": 0}}
    return usage


# Tokens spent on the current question: the total over every API call, and split by call kind
reset_usage()


def record_usage(response, kind):
    # kind: "generation" or "judge"
    for counts in [usage, usage[kind]]:
        counts["input_tokens"] += response.usage.input_tokens
        counts["output_tokens"] += response.usage.output_tokens


def usage_cost(counts, model):
    input_price, output_price = PRICES[model]
    return (counts["input_tokens"] * input_price + counts["output_tokens"] * output_price) / 1_000_000

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


def check_schema(response, min_quote_words):
    # Reject a response cut off by the output token limit
    if response.stop_reason == "max_tokens":
        return None

    # Pull out the answer from the record_answer tool call
    result = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_answer":
            result = block.input
    if not isinstance(result, dict):
        return None

    sentences = result.get("sentences")
    not_covered = result.get("not_covered")
    if not isinstance(sentences, list) or not isinstance(not_covered, list):
        return None
    for s in sentences:
        if not isinstance(s, dict):
            return None
        if not isinstance(s.get("text"), str) or not s["text"].strip():
            return None
        if not isinstance(s.get("cited_doc_id"), str) or not s["cited_doc_id"].strip():
            return None
        if not isinstance(s.get("quote"), str) or len(s["quote"].split()) < min_quote_words:
            return None
        if not isinstance(s.get("heading"), str) or not isinstance(s.get("label"), str):
            return None
    if not all(isinstance(t, str) for t in not_covered):
        return None

    # The output must contain at least one sentence or one uncovered topic
    if not sentences and not not_covered:
        return None
    return result


def generate(query, context, config, strict=False, feedback=None):
    if strict:
        system_prompt = SYSTEM_PROMPT_STRICT
    else:
        system_prompt = SYSTEM_PROMPT

    # First try the prompt as is, then retry once with a reminder to follow the schema
    retry_prompt = system_prompt + "\n\nYou must call record_answer with valid arguments matching its schema exactly."
    for prompt in [system_prompt, retry_prompt]:
        response = client.messages.create(
            model=config["model"],
            max_tokens=config["generation_max_tokens"],
            system=prompt,
            tools=[ANSWER_TOOL],
            tool_choice={"type": "tool", "name": "record_answer"},
            messages=[{"role": "user", "content": build_user_message(query, context, feedback)}],
            # SDK 1.x removed the temperature keyword; Haiku 4.5 still accepts it in the request body
            extra_body={"temperature": config["generation_temperature"]},
        )
        record_usage(response, "generation")

        result = check_schema(response, config["min_quote_words"])
        if result is None:
            continue

        # Only uncovered topics: nothing to verify
        if not result["sentences"]:
            return {"status": "insufficient_info", "sentences": [], "not_covered": result["not_covered"]}
        return {"status": "generated", "sentences": result["sentences"], "not_covered": result["not_covered"]}

    # Model did not return a valid record_answer call after two tries: refuse
    return {"status": "insufficient_info", "sentences": [], "not_covered": []}
