from b1_bm25_only import get_chunk
from b5_retrieval_controller import retrieve, expand
from c2_generate import client, generate, reset_usage, record_usage
from c3_provenance_check import check_provenance
from c4_quote_match import check_quote, locate_quote

INSUFFICIENT_ANSWER = "Insufficient information in the provided Acts."

JUDGE_PROMPT = """Role: You check citations for a Malaysian statutory law assistant.

Action: You are given one statutory section and one sentence that cites it. The passage
the sentence quotes as evidence is marked inside the section with <quote> and </quote>.
Decide whether the section fully supports the sentence, using only the section text and
no outside knowledge. Read the whole section, including any conditions or exceptions it
states, not only the marked passage. The sentence may use plainer wording, but it is not
supported if it adds conditions, exceptions, numbers or consequences that the section
does not state, leaves out a condition or exception that limits what it says, or
contradicts the section.

Expectation: Call record_verdict with the verdict and a one-line reason."""

VERDICT_TOOL = {
    "name": "record_verdict",
    "description": "Record whether the section supports the sentence.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["supported", "not_supported"]},
            "reason": {"type": "string", "description": "One-line reason for the verdict."},
        },
        "required": ["verdict", "reason"],
        "additionalProperties": False,
    },
}


def check_support(sentence, chunk, config):
    # Mark the quoted passage inside the full section text
    text = chunk["full_text"]
    score, start, end = locate_quote(sentence["quote"], text)
    marked = text[:start] + "<quote>" + text[start:end] + "</quote>" + text[end:]

    # The judge sees only the cited section and one sentence, not the question or other sentences
    user_message = f"Section [{chunk['doc_id']}]:\n{marked}\n\nSentence: {sentence['text']}"
    response = client.messages.create(
        model=config["model"],
        max_tokens=config["judge_max_tokens"],
        extra_body={"temperature": config["judge_temperature"]},
        system=JUDGE_PROMPT,
        tools=[VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "record_verdict"},
        messages=[{"role": "user", "content": user_message}],
    )
    record_usage(response, "judge")
    # tool_choice forces the record_verdict call, so the response always contains it
    verdict = next(block.input for block in response.content if block.type == "tool_use")
    return verdict["verdict"], verdict["reason"]


def verify(sentences, retrieved_ids, expanded_ids, config):
    # Run the three checks in order on every sentence; a sentence stops at its first failed check
    checks = []
    for sentence in sentences:
        row = {"sentence": sentence, "provenance": "", "quote_match": "skipped", "support": "skipped", "reason": ""}
        row["provenance"] = check_provenance(sentence, retrieved_ids, expanded_ids)
        if row["provenance"] in ["retrieved", "expanded"]:
            chunk = get_chunk(sentence["cited_doc_id"])
            row["quote_match"] = check_quote(sentence["quote"], chunk["full_text"],
                                             config["min_quote_words"], config["fuzzy_threshold"])
            if row["quote_match"] == "pass":
                row["support"], row["reason"] = check_support(sentence, chunk, config)
        row["passed"] = row["support"] == "supported"
        checks.append(row)
    return checks


def build_feedback(checks):
    # Name each failed sentence and the check it failed, for the stricter prompt
    feedback = []
    for i, row in enumerate(checks, start=1):
        doc_id = row["sentence"]["cited_doc_id"]
        if row["passed"]:
            continue
        # Quote the failed sentence, since the stricter prompt does not see the previous answer
        sentence = f'Sentence {i} ("{row["sentence"]["text"]}")'
        if row["provenance"] == "not_retrieved":
            feedback.append(f"{sentence} cited {doc_id}, which was not among the provided sections.")
        elif row["provenance"] == "nonexistent":
            feedback.append(f"{sentence} cited {doc_id}, which does not exist.")
        elif row["quote_match"] == "fail":
            feedback.append(f"{sentence}: the quote was not found in {doc_id}.")
        else:
            feedback.append(f"{sentence} was not supported by {doc_id}: {row['reason']}")
    return feedback


def answer_query(query, method, config, on_phase=None):
    # on_phase (optional) is called with the name of each phase as it starts, e.g. for a progress display
    def phase(name):
        if on_phase:
            on_phase(name)

    phase(f"Retrieving sections ({method})")
    results = retrieve(query, method, config)
    phase("Expanding cross-references")
    expanded = expand(results, max_expansion=config["max_expansion"])
    retrieved_ids = [doc_id for doc_id, score in results]
    expanded_ids = [doc_id for doc_id, referred_by in expanded]

    # Context set: top-k sections, then expanded sections labelled with the section that referred to them
    context = [(get_chunk(doc_id), None) for doc_id in retrieved_ids]
    context += [(get_chunk(doc_id), referred_by) for doc_id, referred_by in expanded]

    # usage fills in as the generation and judge calls below run
    result = {"query": query, "method": method, "retrieved": results, "expanded": expanded, "attempts": [],
              "usage": reset_usage()}

    # First attempt: initial prompt. Single retry: stricter prompt with feedback, only reached if a sentence failed
    feedback = None
    for strict in [False, True]:
        if strict:
            phase("Regenerating the answer with the stricter prompt")
        else:
            phase("Generating the answer")
        output = generate(query, context, config, strict=strict, feedback=feedback)
        attempt = {"strict": strict, "status": output["status"], "sentences": output["sentences"],
                   "not_covered": output["not_covered"], "checks": []}
        result["attempts"].append(attempt)

        # Only uncovered topics, or no valid output after two tries: verification is skipped
        if output["status"] == "insufficient_info":
            return {**result, "status": "insufficient_info", "sentences": [], "not_covered": output["not_covered"]}

        phase(f"Verifying {len(output['sentences'])} sentences")
        attempt["checks"] = verify(output["sentences"], retrieved_ids, expanded_ids, config)
        if all(row["passed"] for row in attempt["checks"]):
            if strict:
                status = "verified_after_retry"
            else:
                status = "verified"
            return {**result, "status": status, "sentences": output["sentences"], "not_covered": output["not_covered"]}
        feedback = build_feedback(attempt["checks"])

    # Failed again: refuse rather than show an unverified answer
    return {**result, "status": "insufficient_info", "sentences": [], "not_covered": []}


def format_answer(result):
    # The system assembles the displayed answer itself from the verified sentences
    if result["status"] == "insufficient_info":
        return INSUFFICIENT_ANSWER

    # Sentences without a heading are plain paragraphs; each heading starts a new bulleted group
    lines = []
    current_heading = None
    for i, s in enumerate(result["sentences"], start=1):
        heading, label = s["heading"].strip(), s["label"].strip()
        if not heading:
            lines += [f"{s['text']} [{i}]", ""]
            continue
        if heading != current_heading:
            if lines and lines[-1]:
                lines.append("")
            lines.append(f"**{heading}**")
            current_heading = heading
        if label:
            lines.append(f"- **{label}:** {s['text']} [{i}]")
        else:
            lines.append(f"- {s['text']} [{i}]")
    while lines and not lines[-1]:
        lines.pop()

    if result["not_covered"]:
        if lines:
            lines.append("")
        lines.append("The provided Acts do not cover:")
        lines += [f"- {topic}" for topic in result["not_covered"]]
    return "\n".join(lines)

