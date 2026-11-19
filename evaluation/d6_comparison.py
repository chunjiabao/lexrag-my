# Compare the four retrieval methods on every metric (Chapter 3, Section 3.7.6, Table 3.5).
# Run from the project root with: python evaluation/d6_comparison.py
# Reads the results saved by d1-d4, so it makes no API calls. A step that has not been run yet is left out.

import sys
import csv
import json
from pathlib import Path

RESULTS_DIR = Path("results")
RESULTS_PATH = RESULTS_DIR / "d6_comparison.csv"
SENSITIVITY_PATH = RESULTS_DIR / "d6_topk_sensitivity.csv"
METHODS = ["bm25_only", "dense_only", "hybrid_no_rerank", "full"]
# d1 config name for each top_k in the sensitivity table, with the default (main.CONFIG top_k = 5) in the middle
SENSITIVITY_METHOD = "full"
TOP_K_CONFIGS = {"top_k_3": 3, "default": 5, "top_k_10": 10}


if __name__ == "__main__":
    # Each entry: (metric name, {method: value})
    table = []

    path = RESULTS_DIR / "d2_retrieval_metrics.json"
    if path.exists():
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        table += [(f"retrieval {metric}", {m: summary[m][metric] for m in METHODS}) for metric in summary[METHODS[0]]]

    path = RESULTS_DIR / "d4_ragas.json"
    if path.exists():
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        table += [(f"ragas {metric}", {m: summary[m][metric] for m in METHODS})
                  for metric in ["faithfulness", "answer_relevancy"]]

    path = RESULTS_DIR / "d3_verification_metrics.json"
    if path.exists():
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
        table += [(metric, {m: summary[m][metric] for m in METHODS}) for metric in summary[METHODS[0]]]

    path = RESULTS_DIR / "d1_batch_run.json"
    if path.exists():
        runs = json.loads(path.read_text(encoding="utf-8"))
        selected = {m: [r for r in runs if r["method"] == m and r.get("config", "default") == "default"]
                    for m in METHODS}
        table.append(("avg cost per question (USD)",
                      {m: sum(r["cost"] for r in selected[m]) / len(selected[m]) for m in METHODS}))
        table += [(f"avg seconds {stage}",
                   {m: sum(r["seconds"][stage] for r in selected[m]) / len(selected[m]) for m in METHODS})
                  for stage in ["retrieval", "generation", "verification", "total"]]

    print(f"\n  {'metric':<34}" + "".join(f"{m:>18}" for m in METHODS))
    for name, values in table:
        print(f"  {name:<34}" + "".join(f"{values[m]:>18.3f}" for m in METHODS))

    # CSV so the table can be opened in Excel or pasted into the thesis
    with open(RESULTS_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric"] + METHODS)
        for name, values in table:
            writer.writerow([name] + [round(values[m], 4) for m in METHODS])
    print(f"\nSaved to {RESULTS_PATH}")

    # Top-k sensitivity: the proposed system with 3, 5 (default) and 10 sections passed to the model.
    # Retrieval recall at the same k comes from d2, since the top-k is the start of the same ranked list.
    if not (RESULTS_DIR / "d1_batch_run.json").exists():
        sys.exit()
    sensitivity = []
    path = RESULTS_DIR / "d2_retrieval_metrics.json"
    if path.exists():
        summary = json.loads(path.read_text(encoding="utf-8"))["summary"][SENSITIVITY_METHOD]
        sensitivity.append(("retrieval R@k", {c: summary[f"R@{k}"] for c, k in TOP_K_CONFIGS.items()}))
        sensitivity.append(("retrieval P@k", {c: summary[f"P@{k}"] for c, k in TOP_K_CONFIGS.items()}))
    path = RESULTS_DIR / "d4_ragas.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        summaries = {c: saved["summary"] if c == "default" else saved.get("alternatives", {}).get(c)
                     for c in TOP_K_CONFIGS}
        if all(summaries.values()):
            sensitivity += [(f"ragas {metric}", {c: summaries[c][SENSITIVITY_METHOD][metric] for c in TOP_K_CONFIGS})
                            for metric in ["answers", "faithfulness", "answer_relevancy"]]
    path = RESULTS_DIR / "d3_verification_metrics.json"
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        summaries = {c: saved["summary"] if c == "default" else saved["alternatives"].get(c) for c in TOP_K_CONFIGS}
        if all(summaries.values()):
            sensitivity += [(metric, {c: summaries[c][SENSITIVITY_METHOD][metric] for c in TOP_K_CONFIGS})
                            for metric in summaries["default"][SENSITIVITY_METHOD]]
    selected = {c: [r for r in runs if r["method"] == SENSITIVITY_METHOD and r.get("config", "default") == c]
                for c in TOP_K_CONFIGS}
    if all(selected.values()):
        sensitivity.append(("avg retrieved + expanded sections",
                            {c: sum(len(r["retrieved"]) + len(r["expanded"]) for r in selected[c]) / len(selected[c])
                             for c in TOP_K_CONFIGS}))
        sensitivity.append(("avg input tokens per question",
                            {c: sum(r["usage"]["input_tokens"] for r in selected[c]) / len(selected[c])
                             for c in TOP_K_CONFIGS}))
        sensitivity.append(("avg cost per question (USD)",
                            {c: sum(r["cost"] for r in selected[c]) / len(selected[c]) for c in TOP_K_CONFIGS}))
        sensitivity.append(("avg seconds total",
                            {c: sum(r["seconds"]["total"] for r in selected[c]) / len(selected[c])
                             for c in TOP_K_CONFIGS}))

    labels = [f"top_k={k}" for k in TOP_K_CONFIGS.values()]
    print(f"\n  {SENSITIVITY_METHOD}: top-k sensitivity")
    print(f"  {'metric':<34}" + "".join(f"{label:>14}" for label in labels))
    for name, values in sensitivity:
        print(f"  {name:<34}" + "".join(f"{values[c]:>14.3f}" for c in TOP_K_CONFIGS))
    with open(SENSITIVITY_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric"] + labels)
        for name, values in sensitivity:
            writer.writerow([name] + [round(values[c], 4) for c in TOP_K_CONFIGS])
    print(f"\nSaved to {SENSITIVITY_PATH}")
