# Run every test question through the pipeline with each retrieval method (Chapter 3, Section 3.7).
# Run from the project root with: python evaluation/d1_batch_run.py
# Pipeline settings come from main.CONFIG, so the evaluation runs the same system as main.py.
# Uses the Claude API. Results are saved after every run, so a stopped batch continues where it left off.

import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from main import CONFIG
from c0_token_usage import usage_cost
from c5_verify import answer_query, format_answer

TESTSET_PATH = Path("dataset") / "testset" / "testset.json"
RESULTS_PATH = Path("results") / "d1_batch_run.json"
METHODS = ["bm25_only", "dense_only", "hybrid_no_rerank", "full"]
MAX_NEW_RUNS = None             # None runs everything left; a number stops after that many new runs (e.g. a cost check)

# Sensitivity analysis: the number of sections passed to the model, each changing main.CONFIG.
# d2 measures Recall@k for retrieval only; these check whether answer quality depends on top_k.
# Only the proposed system is run again.
ALTERNATIVES = {
    "top_k_3": {"top_k": 3},        # less context: less noise, but more gold sections missed
    "top_k_10": {"top_k": 10},      # more context: more gold sections, but more distracting text
}
ALTERNATIVE_METHODS = ["full"]

# answer_query reports each phase as it starts; the time until the next phase is added to that stage
STAGES = {"Retrieving": "retrieval", "Expanding": "retrieval", "Generating": "generation",
          "Regenerating": "generation", "Verifying": "verification"}


if __name__ == "__main__":
    with open(TESTSET_PATH, encoding="utf-8") as f:
        testset = json.load(f)
    runs = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            runs = json.load(f)
    # Runs saved before the alternatives were added used the default config
    for r in runs:
        r.setdefault("config", "default")
    done = {(r["id"], r["method"], r["config"]) for r in runs}
    configs = [("default", {}, METHODS)] + [(name, changes, ALTERNATIVE_METHODS) for name, changes in ALTERNATIVES.items()]
    todo = [(q, method, config, changes) for config, changes, methods in configs for q in testset for method in methods
            if (q["id"], method, config) not in done]
    total = sum(len(testset) * len(methods) for _, _, methods in configs)

    for q, method, config, changes in todo[:MAX_NEW_RUNS]:
        run_config = {**CONFIG, **changes}
        seconds = {"retrieval": 0.0, "generation": 0.0, "verification": 0.0}
        current = {"stage": None, "start": time.perf_counter()}

        def on_phase(name):
            now = time.perf_counter()
            if current["stage"]:
                seconds[current["stage"]] += now - current["start"]
            current["stage"], current["start"] = STAGES[name.split()[0]], now

        result = answer_query(q["question"], method, run_config, on_phase=on_phase)
        on_phase("Retrieving")      # closes the last stage; the stage it opens is never used

        runs.append({"id": q["id"], "method": method, "config": config, "in_scope": q["in_scope"],
                     "question_type": q["question_type"], "question": q["question"],
                     "status": result["status"], "answer": format_answer(result),
                     "sentences": result["sentences"], "not_covered": result["not_covered"],
                     "retrieved": result["retrieved"], "expanded": result["expanded"],
                     "attempts": result["attempts"], "usage": result["usage"],
                     "cost": usage_cost(result["usage"], run_config),
                     "seconds": {**seconds, "total": sum(seconds.values())}})
        RESULTS_PATH.parent.mkdir(exist_ok=True)
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            # default=float: retrieval scores are numpy floats, which json cannot write directly
            json.dump(runs, f, indent=2, ensure_ascii=False, default=float)
        print(f"{len(runs):>3}/{total} {q['id']} {method:<18} {config:<9} {result['status']:<22} "
              f"${runs[-1]['cost']:.4f} {runs[-1]['seconds']['total']:.1f}s")

    print(f"\nSaved {len(runs)} runs to {RESULTS_PATH}")
    for config, changes, methods in configs:
        for method in methods:
            selected = [r for r in runs if r["method"] == method and r["config"] == config]
            if selected:
                print(f"  {method:<18} {config:<9} total ${sum(r['cost'] for r in selected):.4f}, "
                      f"avg {sum(r['seconds']['total'] for r in selected) / len(selected):.1f}s per question")
