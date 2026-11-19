# RAGAS faithfulness and answer relevancy for the four retrieval methods (Chapter 3, Section 3.7.3).
# Runs in its own environment, because RAGAS needs package versions that would break the retrieval models:
#   venv-ragas\Scripts\python evaluation/d4_ragas.py
# Reads the batch run saved by d1_batch_run.py and scores every in-scope answer that was displayed
# (verified or verified_after_retry). Uses the Claude API as the RAGAS judge; scores are saved after every answer,
# so a stopped run continues where it left off.

import sys
import json
import asyncio
from pathlib import Path
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from ragas.llms import llm_factory
from ragas.embeddings import HuggingFaceEmbeddings
from ragas.metrics.collections import Faithfulness, AnswerRelevancy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from main import CONFIG
from a5_load_chunks import load_all_chunks

BATCH_PATH = Path("results") / "d1_batch_run.json"
RESULTS_PATH = Path("results") / "d4_ragas.json"
METHODS = ["bm25_only", "dense_only", "hybrid_no_rerank", "full"]
DISPLAYED = ["verified", "verified_after_retry"]
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"     # the same embedding model as dense retrieval


if __name__ == "__main__":
    load_dotenv()
    llm = llm_factory(CONFIG["model"], provider="anthropic", client=AsyncAnthropic(),
                      max_tokens=CONFIG["generation_max_tokens"], temperature=CONFIG["judge_temperature"])
    # RAGAS adds top_p by default, but Claude Haiku 4.5 accepts only one of temperature and top_p
    llm.model_args.pop("top_p", None)
    faithfulness = Faithfulness(llm=llm)
    answer_relevancy = AnswerRelevancy(llm=llm, embeddings=HuggingFaceEmbeddings(model=EMBEDDING_MODEL))
    chunks = {c["doc_id"]: c["full_text"] for c in load_all_chunks()}

    with open(BATCH_PATH, encoding="utf-8") as f:
        runs = json.load(f)
    scores = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            scores = json.load(f)["answers"]
    # Scores saved before the d1 sensitivity runs were added used the default config
    for s in scores:
        s.setdefault("config", "default")
    done = {(s["id"], s["method"], s["config"]) for s in scores}
    # One event loop for every call, since the async client keeps its connections on the loop it first ran in
    loop = asyncio.new_event_loop()
    RESULTS_PATH.parent.mkdir(exist_ok=True)

    for r in runs:
        config = r.get("config", "default")
        if not r["in_scope"] or r["status"] not in DISPLAYED or (r["id"], r["method"], config) in done:
            continue
        # The context is what the model was given: the top-k sections, then the expanded sections
        contexts = [chunks[doc_id] for doc_id, score in r["retrieved"]] + [chunks[doc_id] for doc_id, _ in r["expanded"]]
        scores.append({
            "id": r["id"], "method": r["method"], "config": config,
            "faithfulness": loop.run_until_complete(faithfulness.ascore(
                user_input=r["question"], response=r["answer"], retrieved_contexts=contexts)).value,
            "answer_relevancy": loop.run_until_complete(answer_relevancy.ascore(
                user_input=r["question"], response=r["answer"])).value,
        })
        # The summary is added once every answer is scored
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"answers": scores}, f, indent=2)
        print(f"{r['id']} {r['method']:<18} {config:<9} faithfulness {scores[-1]['faithfulness']:.3f} "
              f"answer_relevancy {scores[-1]['answer_relevancy']:.3f}")

    # Mean of each score per method, over the answers that were displayed, for one config of the d1 batch run
    def summarise(config):
        summary = {}
        for method in METHODS:
            selected = [s for s in scores if s["method"] == method and s["config"] == config]
            if config != "default" and not selected:
                continue
            summary[method] = {"answers": len(selected)}
            for metric in ["faithfulness", "answer_relevancy"]:
                summary[method][metric] = sum(s[metric] for s in selected) / len(selected) if selected else None
        return summary

    summary = summarise("default")
    alternatives = {config: summarise(config) for config in dict.fromkeys(s["config"] for s in scores)
                    if config != "default"}

    print(f"\n  {'method':<18}{'config':<10}{'answers':>9}{'faithfulness':>14}{'relevancy':>11}")
    for config, configured in {"default": summary, **alternatives}.items():
        for method, s in configured.items():
            print(f"  {method:<18}{config:<10}{s['answers']:>9}{s['faithfulness'] or 0:>14.3f}"
                  f"{s['answer_relevancy'] or 0:>11.3f}")
    # "summary" is the default config, which d6 reads; the alternatives are kept separately
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "alternatives": alternatives, "answers": scores}, f, indent=2)
    print(f"\nSaved to {RESULTS_PATH}")
