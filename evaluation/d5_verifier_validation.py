# Validate the support check against human labels (Chapter 3, Section 3.7.5).
# Run from the project root with: python evaluation/d5_verifier_validation.py
# Pipeline settings come from main.CONFIG, so the judge is the same one the pipeline uses.
#
# STEP = "build": takes 20 triples from the first attempts of the d1 batch run and 20 altered copies of correct
#   sentences (the alterations use the Claude API), then writes results/d5_triples.csv for labelling.
#   Fill the "label" column with supported or not_supported, and "second_label" for a second labeller if there is one.
# STEP = "score": runs the judge three times on every triple (uses the Claude API; the verdicts are saved, so this
#   happens once) and compares the first run with the labels.

import sys
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from main import CONFIG
from b1_bm25_only import get_chunk
from c2_generate import client
from c4_quote_match import locate_quote
from c5_verify import check_support

STEP = "build"                  # build | score

BATCH_PATH = Path("results") / "d1_batch_run.json"
TRIPLES_PATH = Path("results") / "d5_triples.csv"
JUDGE_PATH = Path("results") / "d5_judge_runs.json"
RESULTS_PATH = Path("results") / "d5_verifier_validation.json"
METHODS = ["bm25_only", "dense_only", "hybrid_no_rerank", "full"]
PER_METHOD = 5                  # 5 sampled and 5 altered triples from each method, 20 + 20 in total
CHANGE_TYPES = ["number", "condition", "party", "negation"]
JUDGE_RUNS = 3
SEED = 42                       # fixed so the same triples are sampled every time
FIELDS = ["triple_id", "source", "method", "question_id", "cited_doc_id", "sentence", "quote", "change_type",
          "original_sentence", "section_text", "label", "second_label"]

ALTER_PROMPT = """Role: You help build a test set for a citation checker on Malaysian statutory law.

Action: You are given a sentence that its cited section supports, and a kind of change. Rewrite the sentence with
exactly one change of that kind, so that the section no longer supports it. Keep the rest of the sentence and its
style the same.
- number: change a number, period, amount or count
- condition: add, remove or change a condition or exception
- party: change who the rule applies to or who must act
- negation: reverse the meaning, for example "may" to "may not"

Expectation: Call record_alteration with the altered sentence."""

ALTER_TOOL = {
    "name": "record_alteration",
    "description": "Record the altered sentence.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {"altered_text": {"type": "string", "description": "The sentence with one change."}},
        "required": ["altered_text"],
        "additionalProperties": False,
    },
}


if __name__ == "__main__" and STEP == "build":
    # Never overwrite a file that may already hold labels
    if TRIPLES_PATH.exists():
        sys.exit(f"{TRIPLES_PATH} already exists; delete it first to build a new set")
    with open(BATCH_PATH, encoding="utf-8") as f:
        runs = json.load(f)
    rng = random.Random(SEED)

    triples = []
    for method in METHODS:
        # Only sentences whose quote passed the quote match reach the support check
        rows = [(r["id"], row) for r in runs if r["method"] == method
                for row in r["attempts"][0]["checks"] if row["quote_match"] == "pass"]
        sampled = rng.sample(rows, PER_METHOD)
        correct = [(qid, row) for qid, row in rows if row["passed"] and (qid, row) not in sampled]

        for qid, row in sampled:
            triples.append({"source": "sampled", "method": method, "question_id": qid, "sentence": row["sentence"]})
        for qid, row in rng.sample(correct, PER_METHOD):
            change_type = CHANGE_TYPES[len([t for t in triples if t["source"] == "altered"]) % len(CHANGE_TYPES)]
            chunk = get_chunk(row["sentence"]["cited_doc_id"])
            response = client.messages.create(
                model=CONFIG["model"],
                max_tokens=CONFIG["judge_max_tokens"],
                extra_body={"temperature": CONFIG["generation_temperature"]},
                system=ALTER_PROMPT,
                tools=[ALTER_TOOL],
                tool_choice={"type": "tool", "name": "record_alteration"},
                messages=[{"role": "user", "content": f"Section [{chunk['doc_id']}]:\n{chunk['full_text']}\n\n"
                                                      f"Sentence: {row['sentence']['text']}\n\nChange: {change_type}"}],
            )
            altered = next(block.input for block in response.content if block.type == "tool_use")["altered_text"]
            # The quote stays the same, so only the sentence differs from a correct triple
            triples.append({"source": "altered", "method": method, "question_id": qid, "change_type": change_type,
                            "original_sentence": row["sentence"]["text"],
                            "sentence": {**row["sentence"], "text": altered}})

    # Shuffle so the labeller cannot tell sampled from altered triples by their position
    rng.shuffle(triples)
    TRIPLES_PATH.parent.mkdir(exist_ok=True)
    # utf-8-sig so Excel shows curly quotes and dashes correctly
    with open(TRIPLES_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, t in enumerate(triples, start=1):
            s = t["sentence"]
            writer.writerow({"triple_id": f"T{i:02d}", "source": t["source"], "method": t["method"],
                             "question_id": t["question_id"], "cited_doc_id": s["cited_doc_id"], "sentence": s["text"],
                             "quote": s["quote"], "change_type": t.get("change_type", ""),
                             "original_sentence": t.get("original_sentence", ""),
                             "section_text": get_chunk(s["cited_doc_id"])["full_text"], "label": "", "second_label": ""})
    print(f"Saved {len(triples)} triples to {TRIPLES_PATH}; label them before running STEP = \"score\"")


if __name__ == "__main__" and STEP == "score":
    with open(TRIPLES_PATH, encoding="utf-8-sig", newline="") as f:
        triples = list(csv.DictReader(f))
    unlabelled = [t["triple_id"] for t in triples if t["label"].strip() not in ["supported", "not_supported"]]
    if unlabelled:
        sys.exit(f"Label every triple first (supported or not_supported); missing: {', '.join(unlabelled)}")

    # Run the judge JUDGE_RUNS times on each triple, saving after each call so a stopped run continues
    judge_runs = {}
    if JUDGE_PATH.exists():
        with open(JUDGE_PATH, encoding="utf-8") as f:
            judge_runs = json.load(f)
    for t in triples:
        while len(judge_runs.get(t["triple_id"], [])) < JUDGE_RUNS:
            chunk = get_chunk(t["cited_doc_id"])
            _, start, end = locate_quote(t["quote"], chunk["full_text"])
            verdict, reason = check_support({"text": t["sentence"]}, chunk, start, end, CONFIG)
            judge_runs.setdefault(t["triple_id"], []).append({"verdict": verdict, "reason": reason})
            with open(JUDGE_PATH, "w", encoding="utf-8") as f:
                json.dump(judge_runs, f, indent=2, ensure_ascii=False)

    # "not_supported" is the positive class: the support check exists to catch unsupported sentences
    pairs = [(t["label"].strip(), judge_runs[t["triple_id"]][0]["verdict"]) for t in triples]
    tp = sum(label == "not_supported" and verdict == "not_supported" for label, verdict in pairs)
    tn = sum(label == "supported" and verdict == "supported" for label, verdict in pairs)
    fp = sum(label == "supported" and verdict == "not_supported" for label, verdict in pairs)
    fn = sum(label == "not_supported" and verdict == "supported" for label, verdict in pairs)
    second = [t for t in triples if t["second_label"].strip()]

    results = {
        "triples": len(triples),
        "confusion_matrix": {"TP": tp, "TN": tn, "FP": fp, "FN": fn},
        "agreement_rate": (tp + tn) / len(triples),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "consistency": sum(len({run["verdict"] for run in judge_runs[t["triple_id"]]}) == 1
                           for t in triples) / len(triples),
        "second_labeller_triples": len(second),
        "labeller_agreement": (sum(t["label"].strip() == t["second_label"].strip() for t in second) / len(second)
                               if second else None),
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    for name, value in results.items():
        print(f"  {name:<24} {value}")
    print(f"\nSaved to {RESULTS_PATH}")
