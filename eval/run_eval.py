"""Run the golden-set evaluation and save real metrics to eval/results/.

Computes four Ragas metrics (faithfulness, answer relevancy, context precision,
context recall) with a Groq judge, plus three custom metrics (hit_rate@k,
citation_accuracy, refusal_accuracy) that need no LLM. Metrics come only from real
runs -- nothing here is hard-coded or invented.

Usage:
  uv run python eval/run_eval.py --config-name baseline
  uv run python eval/run_eval.py --config-name baseline --limit 6
"""

from __future__ import annotations

# --- ragas/langchain compatibility shim -------------------------------------
# ragas 0.4.3 imports langchain_community.chat_models.vertexai.ChatVertexAI at
# load time, but langchain-community 0.4 (the langchain v1 era) removed that path.
# We never use Vertex, so register a harmless stub before importing ragas.
import sys
import types

_stub = types.ModuleType("langchain_community.chat_models.vertexai")
_stub.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules.setdefault("langchain_community.chat_models.vertexai", _stub)
# ----------------------------------------------------------------------------

import argparse
import json
import math
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_groq import ChatGroq
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)
from ragas.run_config import RunConfig

from securerag.config import get_settings
from securerag.evaluation import (
    citation_accuracy,
    hit_rate,
    mean_ignoring_none,
    refusal_correct,
)
from securerag.providers import get_embed_model
from securerag.rag import answer

warnings.filterwarnings("ignore", category=DeprecationWarning)
sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]
GOLDEN = REPO / "eval" / "golden_set.jsonl"
RESULTS_DIR = REPO / "eval" / "results"

# Ragas df column name -> friendly metric name used in our output.
_RAGAS_COLS = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "llm_context_precision_with_reference": "context_precision",
    "context_recall": "context_recall",
}


def _build_judge():
    """Build the Ragas judge chat model from JUDGE_PROVIDER (groq or gemini).

    Putting the judge on Gemini while generation stays on Groq spreads the load
    across two providers' separate free-tier rate limits -> faster eval.
    """
    settings = get_settings()
    provider = settings.judge_provider.lower()
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.judge_model,
            temperature=0,
            google_api_key=settings.google_api_key,
        )
    return ChatGroq(model=settings.judge_model, temperature=0, api_key=settings.groq_api_key)


class _FastembedLC(Embeddings):
    """LangChain Embeddings adapter over our cached fastembed model (for Ragas)."""

    def __init__(self) -> None:
        self._m = get_embed_model()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._m.get_text_embedding(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._m.get_query_embedding(text)


def load_golden(limit: int | None, ids: set[str] | None = None) -> list[dict]:
    """Load the golden set, optionally filtered to `ids` and/or first `limit`."""
    lines = GOLDEN.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    if ids:
        rows = [r for r in rows if r["id"] in ids]
    return rows[:limit] if limit else rows


def _clean(value) -> float | None:
    """Convert a Ragas cell to a float, mapping NaN/None to None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


def run_generation(
    rows: list[dict], delay: float
) -> tuple[list[dict], list[SingleTurnSample], list[str]]:
    """Answer every question and compute the no-LLM custom metrics."""
    settings = get_settings()
    per_question: list[dict] = []
    samples: list[SingleTurnSample] = []
    sample_ids: list[str] = []

    for row in rows:
        result = answer(row["question"])
        retrieved_ids = [r.doc_id for r in result["retrieved"]]
        cited_ids = [c["doc_id"] for c in result["citations"]]
        is_unanswerable = row["category"] == "unanswerable"

        per_question.append(
            {
                "id": row["id"],
                "category": row["category"],
                "question": row["question"],
                "answer": result["answer"],
                "refused": result["refused"],
                "retrieved_doc_ids": retrieved_ids,
                "cited_doc_ids": cited_ids,
                "reference_doc_ids": row["reference_doc_ids"],
                "hit_rate": hit_rate(retrieved_ids, row["reference_doc_ids"]),
                "citation_accuracy": citation_accuracy(cited_ids, row["reference_doc_ids"]),
                "refusal_correct": refusal_correct(result["refused"], is_unanswerable),
            }
        )

        # Ragas only scores answerable questions (a refusal has no reference answer).
        if not is_unanswerable:
            contexts = [r.text for r in result["retrieved"][: settings.answer_context_chunks]]
            samples.append(
                SingleTurnSample(
                    user_input=row["question"],
                    response=result["answer"],
                    retrieved_contexts=contexts,
                    reference=row["reference_answer"],
                )
            )
            sample_ids.append(row["id"])

        if delay:
            time.sleep(delay)

    return per_question, samples, sample_ids


def run_ragas(
    samples: list[SingleTurnSample],
    sample_ids: list[str],
    per_question: list[dict],
    max_workers: int,
) -> None:
    """Score answerable samples with Ragas and merge scores into per_question."""
    judge = LangchainLLMWrapper(_build_judge())
    embeddings = LangchainEmbeddingsWrapper(_FastembedLC())
    run_config = RunConfig(max_workers=max_workers, max_retries=10, max_wait=60)

    result = evaluate(
        EvaluationDataset(samples=samples),
        metrics=[
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ],
        llm=judge,
        embeddings=embeddings,
        run_config=run_config,
    )
    df = result.to_pandas()

    by_id = {rec["id"]: rec for rec in per_question}
    for i, rid in enumerate(sample_ids):
        rec = by_id[rid]
        for col, friendly in _RAGAS_COLS.items():
            if col in df.columns:
                rec[friendly] = _clean(df.iloc[i][col])


def summarise(per_question: list[dict]) -> dict[str, float | None]:
    """Average each metric over the questions where it applies."""
    metrics = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "hit_rate",
        "citation_accuracy",
    ]
    averages: dict[str, float | None] = {
        m: mean_ignoring_none([rec.get(m) for rec in per_question]) for m in metrics
    }
    # refusal_accuracy applies to every question (bool -> 1/0).
    averages["refusal_accuracy"] = mean_ignoring_none(
        [1.0 if rec["refusal_correct"] else 0.0 for rec in per_question]
    )
    return averages


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the golden-set evaluation.")
    parser.add_argument("--config-name", default="baseline", help="Label for this run.")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N questions.")
    parser.add_argument("--ids", default=None, help="Comma-separated question ids (subset).")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds between generations.")
    parser.add_argument("--max-workers", type=int, default=3, help="Ragas concurrency.")
    parser.add_argument(
        "--no-ragas",
        action="store_true",
        help="Skip the LLM-judged Ragas metrics; compute only the custom metrics.",
    )
    args = parser.parse_args()

    load_dotenv()
    settings = get_settings()
    ids = set(args.ids.split(",")) if args.ids else None
    rows = load_golden(args.limit, ids)

    print(f"Running eval '{args.config_name}' on {len(rows)} questions...")
    per_question, samples, sample_ids = run_generation(rows, args.delay)
    if args.no_ragas:
        print("Skipping Ragas (--no-ragas); computing custom metrics only.")
    else:
        print(f"Generation done. Scoring {len(samples)} answerable questions with Ragas...")
        run_ragas(samples, sample_ids, per_question, args.max_workers)

    averages = summarise(per_question)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{datetime.now(UTC).strftime('%Y%m%d')}_{args.config_name}.json"
    payload = {
        "config_name": args.config_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "params": {
            "generator": settings.llm_model,
            "judge": settings.judge_model,
            "retrieval_top_k": settings.retrieval_top_k,
            "answer_context_chunks": settings.answer_context_chunks,
            "hybrid_enabled": settings.hybrid_enabled,
            "rerank_enabled": settings.rerank_enabled,
            "n_questions": len(rows),
            "ragas_scored": not args.no_ragas,
        },
        "averages": averages,
        "per_question": per_question,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nSaved: {out_path.relative_to(REPO)}")
    print("Averages:")
    for name, value in averages.items():
        print(f"  {name:20s}: {value:.4f}" if value is not None else f"  {name:20s}: n/a")


if __name__ == "__main__":
    main()
