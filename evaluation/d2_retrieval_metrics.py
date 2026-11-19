# Precision@k and Recall@k for the four retrieval methods (Chapter 3, Section 3.7).
# Run from the project root with: python evaluation/d2_retrieval_metrics.py
# Pipeline settings come from main.CONFIG, so the evaluation runs the same system as main.py.

import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from main import CONFIG
from b5_retrieval_controller import retrieve

TESTSET_PATH = Path("dataset") / "testset" / "testset.json"
RESULTS_PATH = Path("results") / "d2_retrieval_metrics.json"
METHODS = ["bm25_only", "dense_only", "hybrid_no_rerank", "full"]
EVAL_K = [1, 3, 5, 10]          # k values for Precision@k and Recall@k

# Sensitivity analysis: alternative settings for the fusion and reranking steps, each changing main.CONFIG.
# The default comes from prior work; these check whether the results depend on it. Only the methods that use
# these settings are run again.
ALTERNATIVES = {
    "A_shallow_rerank": {"candidate_k": 10},                    # fewer candidates for the reranker
    "B_deep_rerank": {"retriever_k": 50, "candidate_k": 50},    # deeper search and reranking
    "C_lower_rrf_k": {"rrf_k": 20},                             # fusion favours the top ranks more
}
ALTERNATIVE_METHODS = ["hybrid_no_rerank", "full"]


def summarise(rows, config="default", question_type=None):
    # Mean Precision@k, Recall@k and retrieval time per method for one config,
    # over all in-scope questions or one question type
    summary = {}
    for method in METHODS if config == "default" else ALTERNATIVE_METHODS:
        selected = [r for r in rows if r["config"] == config and r["method"] == method
                    and question_type in (None, r["type"])]
        summary[method] = {f"{m}@{k}": sum(r[f"{m}@{k}"] for r in selected) / len(selected)
                           for k in EVAL_K for m in ["P", "R"]}
        summary[method]["avg_seconds"] = sum(r["seconds"] for r in selected) / len(selected)
    return summary


if __name__ == "__main__":
    with open(TESTSET_PATH, encoding="utf-8") as f:
        testset = json.load(f)

    rows = []
    runs = [("default", {}, method) for method in METHODS]
    runs += [(name, changes, method) for name, changes in ALTERNATIVES.items() for method in ALTERNATIVE_METHODS]
    for config, changes, method in runs:
        # Retrieve the largest k once; the top-k for each smaller k is the start of the same ranked list
        retrieve_config = {**CONFIG, **changes, "top_k": max(EVAL_K)}
        # One untimed call first, so one-off start-up work is not counted as retrieval time
        retrieve(testset[0]["question"], method, retrieve_config)
        # Out-of-scope questions have no gold sections, so they are left out of the retrieval metrics
        for q in [q for q in testset if q["in_scope"]]:
            # Chunk doc_ids are lowercase after "#" (Act265#60fa), the testset uses the printed form (Act265#60FA)
            gold_ids = [act + "#" + section.lower() for act, section in (g.split("#") for g in q["gold_doc_ids"])]
            start = time.perf_counter()
            retrieved_ids = [doc_id for doc_id, score in retrieve(q["question"], method, retrieve_config)]
            seconds = time.perf_counter() - start
            row = {"id": q["id"], "type": q["question_type"], "config": config, "method": method, "gold": gold_ids,
                   "retrieved": retrieved_ids, "seconds": seconds}
            for k in EVAL_K:
                hits = len(set(retrieved_ids[:k]) & set(gold_ids))
                row[f"P@{k}"], row[f"R@{k}"] = hits / k, hits / len(gold_ids)
            rows.append(row)

    for config in ["default", *ALTERNATIVES]:
        for question_type in [None, "exact_term", "paraphrase", "distractor"]:
            print(f"\n{config}: {question_type or 'All in-scope questions'}")
            print(f"  {'method':<18}" + "".join(f"{m + '@' + str(k):>8}" for m in ["P", "R"] for k in EVAL_K)
                  + f"{'avg sec':>9}")
            for method, scores in summarise(rows, config, question_type).items():
                print(f"  {method:<18}" + "".join(f"{scores[m + '@' + str(k)]:>8.3f}" for m in ["P", "R"] for k in EVAL_K)
                      + f"{scores['avg_seconds']:>9.3f}")

    # "summary" is the default config, which d6 reads; the alternatives are kept separately
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summarise(rows),
                   "alternatives": {name: {"changes": changes, "summary": summarise(rows, name)}
                                    for name, changes in ALTERNATIVES.items()},
                   "questions": rows}, f, indent=2)
    print(f"\nSaved to {RESULTS_PATH}")
