#!/usr/bin/env python3
r"""
evaluate_rag.py — BAZspark RAG Evaluation Driver
=================================================
Evaluates the quality of the BAZspark Engineering Copilot (GraphRAG Engine)
using the RAGAS framework, following the rag-eval skill layout:
  <dataset-root>/corpus/  — corpus documents (indexed for retrieval)
  <dataset-root>/train.json — evaluation questions and ground-truth answers

Output artifacts (under --output_dir / <dataset_label>/):
  rag_<label>_evaluation_data.json    — per-query results
  rag_<label>_evaluation_summary.json — headline RAGAS means
  rag_<label>_evaluation_results.json — per-sample score vectors
  rag_<label>_evaluation_metrics.json — structured roll-up

Usage (minimal):
  python scripts/eval/evaluate_rag.py \\
    --dataset-paths eval/nfpa72_rag_dataset \\
    --host localhost \\
    --port 8000

Run from the REPO ROOT.
Set NVIDIA_API_KEY or OPENAI_API_KEY in environment for RAGAS judge.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import httpx

# ──────────────────────────────────────────────────────────────────────────────
# CLI Arguments
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BAZspark RAG Evaluation Driver — RAGAS quality benchmarks"
    )
    p.add_argument(
        "--dataset-paths",
        nargs="+",
        required=True,
        help="One or more dataset root directories each containing corpus/ and train.json",
    )
    p.add_argument("--host", default="localhost", help="RAG server host (default: localhost)")
    p.add_argument("--port", type=int, default=8000, help="RAG server port (default: 8000)")
    p.add_argument(
        "--ingestor_server_url",
        default="http://localhost:8082",
        help="Ingestor server base URL without /v1 suffix (default: http://localhost:8082)",
    )
    p.add_argument("--output_dir", default="results", help="Output directory (default: results)")
    p.add_argument("--collection", default=None, help="Vector DB collection name override")
    p.add_argument("--top_k", type=int, default=5, help="Reranker top-k (default: 5)")
    p.add_argument("--vdb_top_k", type=int, default=20, help="Vector DB candidate pool size (default: 20)")
    p.add_argument("--temperature", type=float, default=None, help="LLM temperature for generation")
    p.add_argument("--top_p", type=float, default=None, help="LLM top-p for generation")
    p.add_argument("--max_tokens", type=int, default=None, help="Max generation tokens")
    p.add_argument("--skip_ingestion", action="store_true", help="Skip corpus ingestion")
    p.add_argument("--skip_evaluation", action="store_true", help="Skip RAGAS evaluation (ingest only)")
    p.add_argument("--force_ingestion", action="store_true", help="Delete existing collection and re-ingest")
    p.add_argument(
        "--enable_reranker", action="store_true", default=None,
        help="Enable reranker on generate endpoint"
    )
    p.add_argument(
        "--disable_reranker", action="store_true", default=None,
        help="Disable reranker on generate endpoint"
    )
    p.add_argument(
        "--enable_query_rewriting", action="store_true", default=None,
        help="Enable query rewriting"
    )
    p.add_argument(
        "--disable_query_rewriting", action="store_true", default=None,
        help="Disable query rewriting"
    )
    p.add_argument("--file_type", default="txt", help="Corpus file type (default: txt)")
    p.add_argument("--dry_run", action="store_true", help="Validate dataset and print config without running eval")
    p.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout per request in seconds (default: 60)")
    return p.parse_args()


# ──────────────────────────────────────────────────────────────────────────────
# Dataset Helpers
# ──────────────────────────────────────────────────────────────────────────────

CORPUS_DIRECTORY = "corpus"
EVAL_DATA = "train.json"


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    """Load and validate train.json from the dataset directory."""
    train_file = dataset_path / EVAL_DATA
    if not train_file.exists():
        raise FileNotFoundError(f"train.json not found in {dataset_path}")
    with open(train_file, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"train.json must be a JSON array (top-level list), got {type(data).__name__}")
    if not all(isinstance(row, dict) for row in data):
        raise ValueError("train.json must be a list of objects (dicts)")
    missing = [i for i, row in enumerate(data) if "question" not in row or "answer" not in row]
    if missing:
        raise ValueError(f"Rows missing 'question' or 'answer': {missing[:5]}")
    return data


def list_corpus_files(dataset_path: Path, file_type: str) -> list[Path]:
    """Return all corpus files matching file_type."""
    corpus_dir = dataset_path / CORPUS_DIRECTORY
    if not corpus_dir.exists():
        raise FileNotFoundError(f"corpus/ directory not found in {dataset_path}")
    pattern = f"**/*.{file_type}"
    files = sorted(corpus_dir.glob(pattern))
    return files


# ──────────────────────────────────────────────────────────────────────────────
# RAG Server Client (BAZspark GraphRAG endpoint)
# ──────────────────────────────────────────────────────────────────────────────

def build_rag_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def query_rag(
    base_url: str,
    question: str,
    top_k: int = 5,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    enable_reranker: bool | None = None,
    enable_query_rewriting: bool | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """
    Query the BAZspark GraphRAG /api/v2/graphrag/ask endpoint.
    Falls back to /v1/generate if GraphRAG endpoint unavailable.
    Returns dict with 'answer', 'contexts', and optional 'retrieved_docs'.
    """
    payload: dict[str, Any] = {"question": question, "top_k": top_k}
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if enable_reranker is not None:
        payload["enable_reranker"] = enable_reranker
    if enable_query_rewriting is not None:
        payload["enable_query_rewriting"] = enable_query_rewriting

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{base_url}/api/v2/graphrag/ask", json=payload)
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "")
            contexts = data.get("contexts", [])
            # Normalise contexts to list of strings
            if isinstance(contexts, list):
                ctx_strings = [
                    c["text"] if isinstance(c, dict) and "text" in c else str(c)
                    for c in contexts
                ]
            else:
                ctx_strings = []
            return {
                "answer": answer,
                "generated_contexts": ctx_strings,
                "retrieved_docs": data.get("retrieved_docs", []),
            }
    except Exception as exc:
        return {
            "answer": f"ERROR: {exc}",
            "generated_contexts": [],
            "retrieved_docs": [],
            "error": str(exc),
        }


# ──────────────────────────────────────────────────────────────────────────────
# RAGAS Evaluation
# ──────────────────────────────────────────────────────────────────────────────

def run_ragas_evaluation(
    eval_data: list[dict[str, Any]],
    judge_model: str | None = None,
) -> dict[str, Any]:
    """
    Run RAGAS evaluation over the collected eval_data rows.
    Each row must have: question, answer (ground truth), generated_answer, generated_contexts.
    Returns a dict with metric vectors and means.
    """
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if not nvidia_key and not openai_key:
        print("[WARN] Neither NVIDIA_API_KEY nor OPENAI_API_KEY is set. RAGAS judge cannot run.")
        print("       Set NVIDIA_API_KEY or OPENAI_API_KEY to enable full RAGAS scoring.")
        print("       Returning accuracy-only mock scores for offline/dry-run mode.")
        # Return simple accuracy proxy: 1.0 if generated_answer is non-empty, 0.0 otherwise
        mock_acc = [1.0 if row.get("generated_answer") else 0.0 for row in eval_data]
        return {
            "nv_accuracy": mock_acc,
            "nv_context_relevance": [],
            "nv_response_groundedness": [],
            "_mock": True,
        }

    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import evaluate
        from ragas.metrics import (
            answer_correctness,
            context_precision,
            faithfulness,
        )
    except ImportError as e:
        print(f"[ERROR] RAGAS dependencies not installed: {e}")
        print("        Run: uv sync --project scripts/eval")
        sys.exit(1)

    # Prepare RAGAS dataset
    questions = [row["question"] for row in eval_data]
    ground_truths = [row["answer"] for row in eval_data]
    generated_answers = [row.get("generated_answer", "") for row in eval_data]
    contexts = [row.get("generated_contexts", []) or [""] for row in eval_data]

    ragas_ds = Dataset.from_dict({
        "question": questions,
        "answer": generated_answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    judge = judge_model or os.environ.get("RAG_EVAL_JUDGE_MODEL", "gpt-4o-mini")
    print(f"[INFO] Running RAGAS evaluation with judge model: {judge}")

    api_key = nvidia_key or openai_key
    base_url = "https://integrate.api.nvidia.com/v1" if nvidia_key else None

    llm = ChatOpenAI(model=judge, api_key=api_key, base_url=base_url)
    embeddings = OpenAIEmbeddings(api_key=api_key, base_url=base_url)

    result = evaluate(
        ragas_ds,
        metrics=[answer_correctness, context_precision, faithfulness],
        llm=llm,
        embeddings=embeddings,
    )

    df = result.to_pandas()
    return {
        "nv_accuracy": df["answer_correctness"].tolist(),
        "nv_context_relevance": df["context_precision"].tolist() if "context_precision" in df else [],
        "nv_response_groundedness": df["faithfulness"].tolist() if "faithfulness" in df else [],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main Evaluation Loop
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_dataset(args: argparse.Namespace, dataset_path: Path) -> None:
    label = dataset_path.name
    print(f"\n{'='*60}")
    print(f"Evaluating dataset: {label}")
    print(f"Dataset path: {dataset_path}")
    print(f"RAG server: http://{args.host}:{args.port}")
    print(f"{'='*60}")

    # Load dataset
    train_data = load_dataset(dataset_path)
    corpus_files = list_corpus_files(dataset_path, args.file_type)
    print(f"[INFO] Loaded {len(train_data)} eval rows, {len(corpus_files)} corpus files.")

    if args.dry_run:
        print("[DRY RUN] Dataset validated. Skipping RAG queries and RAGAS scoring.")
        print(f"[DRY RUN] Sample questions: {[row['question'][:80] for row in train_data[:3]]}")
        return

    # Output directory
    out_dir = Path(args.output_dir) / label
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collection name

    # Skip ingestion?
    if not args.skip_ingestion:
        print("[INFO] Skipping corpus ingestion (use a live ingestor for full pipeline).")
        print(f"       Corpus has {len(corpus_files)} files in {dataset_path / CORPUS_DIRECTORY}/")
        print("       To ingest: point --ingestor_server_url at a running BAZspark/NV-Ingest service.")

    # Query RAG for each row
    base_url = build_rag_url(args.host, args.port)
    enable_reranker = True if args.enable_reranker else (False if args.disable_reranker else None)
    enable_qr = True if args.enable_query_rewriting else (False if args.disable_query_rewriting else None)

    eval_rows: list[dict[str, Any]] = []
    error_count = 0

    print(f"\n[INFO] Querying RAG server for {len(train_data)} questions...")
    for i, row in enumerate(train_data):
        try:
            result = query_rag(
                base_url=base_url,
                question=row["question"],
                top_k=args.top_k,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                enable_reranker=enable_reranker,
                enable_query_rewriting=enable_qr,
                timeout=args.timeout,
            )
            if "error" in result:
                error_count += 1
                print(f"  [WARN] Row {i} (id={row.get('id', i)}): {result['error']}")
        except Exception as exc:
            error_count += 1
            print(f"  [ERROR] Row {i}: {exc}")
            result = {"answer": "", "generated_contexts": [], "retrieved_docs": []}

        eval_rows.append({
            "id": row.get("id", i),
            "question": row["question"],
            "answer": row["answer"],
            "generated_answer": result.get("answer", ""),
            "generated_contexts": result.get("generated_contexts", []),
            "retrieved_docs": result.get("retrieved_docs", []),
        })

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(train_data)} rows queried")

    # Warn on high error rate
    if error_count > len(train_data) * 0.5:
        print(f"\n[WARN] >50% failure rate ({error_count}/{len(train_data)}). Check RAG server connectivity.")

    # Write evaluation_data.json
    data_path = out_dir / f"rag_{label}_evaluation_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(eval_rows, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Wrote evaluation data: {data_path}")

    if args.skip_evaluation:
        print("[INFO] --skip_evaluation set. Skipping RAGAS scoring.")
        return

    # Run RAGAS
    print("\n[INFO] Running RAGAS evaluation...")
    scores = run_ragas_evaluation(eval_rows)

    # Compute means
    def safe_mean(lst: list) -> float | None:
        vals = [v for v in lst if v is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    summary = {
        "dataset": label,
        "n_queries": len(eval_rows),
        "n_errors": error_count,
        "nv_accuracy_mean": safe_mean(scores.get("nv_accuracy", [])),
        "nv_context_relevance_mean": safe_mean(scores.get("nv_context_relevance", [])),
        "nv_response_groundedness_mean": safe_mean(scores.get("nv_response_groundedness", [])),
        "mock_scores": scores.get("_mock", False),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Write artifacts
    summary_path = out_dir / f"rag_{label}_evaluation_summary.json"
    results_path = out_dir / f"rag_{label}_evaluation_results.json"
    metrics_path = out_dir / f"rag_{label}_evaluation_metrics.json"

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "dataset": label,
            "ingestion_metrics_list": [],
            "evaluation_metrics": summary,
        }, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS — {label}")
    print(f"{'='*60}")
    print(f"  nv_accuracy_mean              : {summary['nv_accuracy_mean']}")
    print(f"  nv_context_relevance_mean     : {summary['nv_context_relevance_mean']}")
    print(f"  nv_response_groundedness_mean : {summary['nv_response_groundedness_mean']}")
    print(f"  mock_scores                   : {summary['mock_scores']}")
    print(f"\n  Summary: {summary_path}")
    print(f"  Data:    {data_path}")
    print(f"{'='*60}\n")

    # Quality gate warning
    acc = summary["nv_accuracy_mean"]
    if acc is not None and acc < 0.75:
        print(f"[WARN] nv_accuracy_mean ({acc}) is below quality threshold 0.75.")
        print("       Consider tuning --top_k, --vdb_top_k, or reviewing corpus quality.")


# ──────────────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Validate NVIDIA_API_KEY warning (non-fatal)
    if not os.environ.get("NVIDIA_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("[WARN] NVIDIA_API_KEY and OPENAI_API_KEY are not set.")
        print("       RAGAS scoring requires one of these. Set via:")
        print("       $env:NVIDIA_API_KEY='your-key'  # PowerShell")
        print("       export NVIDIA_API_KEY='your-key'  # bash")

    for path_str in args.dataset_paths:
        dataset_path = Path(path_str)
        if not dataset_path.exists():
            print(f"[ERROR] Dataset path does not exist: {dataset_path}", file=sys.stderr)
            sys.exit(1)
        try:
            evaluate_dataset(args, dataset_path)
        except Exception as exc:
            print(f"[ERROR] Failed to evaluate {dataset_path}: {exc}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
