# Citation verification metrics for the four retrieval methods (Chapter 3, Section 3.7.4).
# Run from the project root with: python evaluation/d3_verification_metrics.py
# Reads the batch run saved by d1_batch_run.py, so it makes no API calls.

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from b1_bm25_only import corpus

TESTSET_PATH = Path("dataset") / "testset" / "testset.json"
BATCH_PATH = Path("results") / "d1_batch_run.json"
RESULTS_PATH = Path("results") / "d3_verification_metrics.json"
METHODS = ["bm25_only", "dense_only", "hybrid_no_rerank", "full"]
STATUSES = ["verified", "verified_after_retry", "insufficient_info", "generation_error"]
DISPLAYED = ["verified", "verified_after_retry"]


def gold_recall(r, gold):
    # Share of a question's gold sections cited somewhere in its answer
    cited_ids = {s["cited_doc_id"] for s in r["sentences"]}
    return len(cited_ids & set(gold[r["id"]])) / len(gold[r["id"]])


def summarise(runs, gold, corpus_ids, config="default"):
    # Verification metrics per method for one config of the d1 batch run
    summary = {}
    for method in METHODS:
        selected = [r for r in runs if r["method"] == method and r.get("config", "default") == config]
        if not selected:
            continue
        in_scope = [r for r in selected if r["in_scope"]]
        out_of_scope = [r for r in selected if not r["in_scope"]]
        displayed = [r for r in in_scope if r["status"] in DISPLAYED]
        multi = [r for r in displayed if len(gold[r["id"]]) > 1]

        # Every sentence of every first-attempt answer; a run that stopped before generating has no checks
        first = [row for r in selected for row in r["attempts"][0]["checks"]]
        # A citation outside the context is split by whether the section exists anywhere in the corpus
        not_retrieved = [row for row in first if row["provenance"] == "not_provided"
                         and row["sentence"]["cited_doc_id"] in corpus_ids]
        nonexistent = [row for row in first if row["provenance"] == "not_provided"
                       and row["sentence"]["cited_doc_id"] not in corpus_ids]

        # Each displayed answer counts each cited section once, even if several sentences cite it
        cited = [(r, doc_id) for r in displayed for doc_id in {s["cited_doc_id"] for s in r["sentences"]}]
        expanded = [(r, doc_id) for r, doc_id in cited if doc_id in [e[0] for e in r["expanded"]]]

        summary[method] = {
            **{s: sum(r["status"] == s for r in in_scope) / len(in_scope) for s in STATUSES},
            "out_of_scope_refused": sum(r["status"] == "insufficient_info" for r in out_of_scope) / len(out_of_scope),
            "answer_coverage": len(displayed) / len(in_scope),
            "fail_not_retrieved": len(not_retrieved) / len(first),
            "fail_nonexistent": len(nonexistent) / len(first),
            "fail_quote_match": sum(row["quote_match"] == "fail" for row in first) / len(first),
            "fail_support": sum(row["support"] == "not_supported" for row in first) / len(first),
            # Citation precision (Section 2.6.1): first-attempt sentences that pass the support check
            "citation_precision": sum(row["passed"] for row in first) / len(first),
            # Gold-based citation precision at section level: cited sections that are gold sections
            "gold_citation_rate": sum(doc_id in gold[r["id"]] for r, doc_id in cited) / len(cited),
            # Citation recall (Section 3.7.4): share of a question's gold sections cited in its displayed answer
            "citation_recall_gold": sum(gold_recall(r, gold) for r in displayed) / len(displayed),
            # End-to-end citation recall: refused or failed in-scope questions count as 0
            "citation_recall_gold_all": sum(gold_recall(r, gold) for r in displayed) / len(in_scope),
            # Citation recall over displayed answers whose question needs more than one gold section
            "citation_recall_gold_multi": sum(gold_recall(r, gold) for r in multi) / len(multi),
            # Displayed answers that cite every gold section of their question
            "all_gold_cited_rate": sum(gold_recall(r, gold) == 1 for r in displayed) / len(displayed),
            "expansion_share": len(expanded) / len(cited),
            # Counts behind the shares above
            "in_scope_questions": len(in_scope),
            "first_attempt_sentences": len(first),
            "cited_sections": len(cited),
            "displayed_answers": len(displayed),
            "multi_section_displayed": len(multi),
            "gold_sections_in_displayed": sum(len(gold[r["id"]]) for r in displayed),
        }
    return summary


if __name__ == "__main__":
    with open(TESTSET_PATH, encoding="utf-8") as f:
        testset = json.load(f)
    with open(BATCH_PATH, encoding="utf-8") as f:
        runs = json.load(f)
    # Chunk doc_ids are lowercase after "#" (Act265#60fa), the testset uses the printed form (Act265#60FA)
    gold = {q["id"]: [act + "#" + section.lower() for act, section in (g.split("#") for g in q["gold_doc_ids"])]
            for q in testset}
    corpus_ids = {c["doc_id"] for c in corpus}

    summary = summarise(runs, gold, corpus_ids)
    # Sensitivity runs from d1 (e.g. top_k_3), each a separate config
    alternatives = {config: summarise(runs, gold, corpus_ids, config)
                    for config in dict.fromkeys(r.get("config", "default") for r in runs) if config != "default"}

    for config, scores in {"default": summary, **alternatives}.items():
        methods = list(scores)
        print(f"\n{config}")
        print(f"  {'metric':<26}" + "".join(f"{m:>18}" for m in methods))
        for metric in scores[methods[0]]:
            print(f"  {metric:<26}" + "".join(f"{scores[m][metric]:>18.3f}" for m in methods))

    # Error analysis (printed only): displayed multi-section answers from full that miss a gold section
    print("\nfull, default: displayed multi-section answers missing a gold section")
    for r in runs:
        if (r["method"] == "full" and r.get("config", "default") == "default" and r["in_scope"]
                and r["status"] in DISPLAYED and len(gold[r["id"]]) > 1 and gold_recall(r, gold) < 1):
            cited_ids = sorted({s["cited_doc_id"] for s in r["sentences"]})
            print(f"  {r['id']}  gold {gold[r['id']]}  cited {cited_ids}")

    # "summary" is the default config, which d6 reads; the alternatives are kept separately
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "alternatives": alternatives}, f, indent=2)
    print(f"\nSaved to {RESULTS_PATH}")
