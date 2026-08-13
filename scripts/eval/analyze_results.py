#!/usr/bin/env python3
r"""
analyze_results.py — BAZspark RAG Evaluation Result Analyzer
============================================================
Analyzes RAGAS output artifacts from evaluate_rag.py.
Produces: per-query accuracy table, worst-queries report, CSV export,
and Markdown summary suitable for PR descriptions.

Usage:
  # Analyze results for a dataset
  python scripts/eval/analyze_results.py \\
    --dataset nfpa72_rag_dataset \\
    --results-dir results

  # Export CSV
  python scripts/eval/analyze_results.py \\
    --dataset nfpa72_rag_dataset --export-csv

  # Generate Markdown report
  python scripts/eval/analyze_results.py \\
    --dataset nfpa72_rag_dataset --markdown

Run from the REPO ROOT.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Loader
# ──────────────────────────────────────────────────────────────────────────────

def load_results(results_dir: Path, label: str) -> tuple[list, dict, dict]:
    """Load evaluation_data, evaluation_results, evaluation_summary for a dataset."""
    base = results_dir / label

    data_file = base / f"rag_{label}_evaluation_data.json"
    scores_file = base / f"rag_{label}_evaluation_results.json"
    summary_file = base / f"rag_{label}_evaluation_summary.json"

    if not data_file.exists():
        print(f"[ERROR] Data file not found: {data_file}", file=sys.stderr)
        sys.exit(1)
    if not scores_file.exists():
        print(f"[ERROR] Scores file not found: {scores_file}", file=sys.stderr)
        sys.exit(1)

    with open(data_file, encoding="utf-8") as f:
        data = json.load(f)
    with open(scores_file, encoding="utf-8") as f:
        scores = json.load(f)
    summary = {}
    if summary_file.exists():
        with open(summary_file, encoding="utf-8") as f:
            summary = json.load(f)

    return data, scores, summary


# ──────────────────────────────────────────────────────────────────────────────
# Table Printers
# ──────────────────────────────────────────────────────────────────────────────

def print_worst_queries(data: list, scores: dict, top_n: int = 10) -> list[dict]:
    """Print per-query table sorted by accuracy (worst first)."""
    acc_list = scores.get("nv_accuracy", [])
    ctx_list = scores.get("nv_context_relevance", [None] * len(data))
    grd_list = scores.get("nv_response_groundedness", [None] * len(data))

    rows = []
    for i, d in enumerate(data):
        acc = acc_list[i] if i < len(acc_list) else None
        rows.append({
            "i": i,
            "id": d.get("id", i),
            "question": d["question"][:80],
            "nv_accuracy": acc,
            "nv_context_relevance": ctx_list[i] if i < len(ctx_list) else None,
            "nv_response_groundedness": grd_list[i] if i < len(grd_list) else None,
            "has_context": bool(d.get("generated_contexts")),
            "answer_len": len(d.get("generated_answer", "")),
        })

    rows.sort(key=lambda r: (r["nv_accuracy"] is None, r["nv_accuracy"] or 0.0))

    print(f"\n{'─'*90}")
    print(f"{'i':>4}  {'id':>5}  {'acc':>5}  {'ctx_rel':>7}  {'grnd':>5}  {'ctx?':>4}  question")
    print(f"{'─'*90}")
    for r in rows[:top_n]:
        acc_s = f"{r['nv_accuracy']:.3f}" if r["nv_accuracy"] is not None else "  —  "
        ctx_s = f"{r['nv_context_relevance']:.3f}" if r["nv_context_relevance"] is not None else "  —  "
        grd_s = f"{r['nv_response_groundedness']:.3f}" if r["nv_response_groundedness"] is not None else "  —  "
        ctx_flag = "Y" if r["has_context"] else "N"
        print(f"{r['i']:>4}  {str(r['id']):>5}  {acc_s:>5}  {ctx_s:>7}  {grd_s:>5}  {ctx_flag:>4}  {r['question']}")
    print(f"{'─'*90}")
    print("(has_context=N with low accuracy → retrieval gap, not generation problem)")
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# CSV Export
# ──────────────────────────────────────────────────────────────────────────────

def export_csv(data: list, scores: dict, out_path: Path) -> None:
    """Export full results to CSV."""
    acc = scores.get("nv_accuracy", [None] * len(data))
    ctxr = scores.get("nv_context_relevance", [None] * len(data))
    grd = scores.get("nv_response_groundedness", [None] * len(data))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id", "question", "answer", "generated_answer",
                "nv_accuracy", "nv_context_relevance", "nv_response_groundedness",
                "has_context", "answer_length",
            ],
        )
        w.writeheader()
        for i, d in enumerate(data):
            w.writerow({
                "id": d.get("id", i),
                "question": d["question"],
                "answer": d["answer"],
                "generated_answer": d.get("generated_answer", ""),
                "nv_accuracy": acc[i] if i < len(acc) else None,
                "nv_context_relevance": ctxr[i] if i < len(ctxr) else None,
                "nv_response_groundedness": grd[i] if i < len(grd) else None,
                "has_context": bool(d.get("generated_contexts")),
                "answer_length": len(d.get("generated_answer", "")),
            })
    print(f"[OK] CSV exported: {out_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Markdown Report
# ──────────────────────────────────────────────────────────────────────────────

def generate_markdown(
    data: list, scores: dict, summary: dict, label: str, top_n: int = 5
) -> str:
    """Generate Markdown table of worst queries for PR descriptions."""
    acc_list = scores.get("nv_accuracy", [])
    pairs = sorted(
        zip(acc_list, data, strict=False),
        key=lambda x: (x[0] is None, x[0] or 0.0)
    )

    n_queries = summary.get("n_queries", len(data))
    n_errors = summary.get("n_errors", 0)
    acc_mean = summary.get("nv_accuracy_mean", "—")
    ctx_mean = summary.get("nv_context_relevance_mean", "—")
    grd_mean = summary.get("nv_response_groundedness_mean", "—")
    mock = summary.get("mock_scores", False)
    ts = summary.get("timestamp", "—")

    lines = [
        f"## RAG Evaluation Report — `{label}`",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Dataset | `{label}` |",
        f"| Queries | {n_queries} |",
        f"| Errors | {n_errors} |",
        f"| `nv_accuracy_mean` | {acc_mean} |",
        f"| `nv_context_relevance_mean` | {ctx_mean} |",
        f"| `nv_response_groundedness_mean` | {grd_mean} |",
        f"| Mock Scores | {'⚠️ Yes (no API key)' if mock else '✅ No'} |",
        f"| Timestamp | {ts} |",
        "",
        f"### Worst {top_n} Queries by Accuracy",
        "",
        "| id | acc | question | generated_answer |",
        "|----|-----|----------|-----------------|",
    ]

    for acc, d in pairs[:top_n]:
        acc_s = f"{acc:.3f}" if acc is not None else "—"
        q = d["question"][:60].replace("|", "\\|")
        a = d.get("generated_answer", "")[:80].replace("|", "\\|")
        row_id = d.get("id", "—")
        lines.append(f"| {row_id} | {acc_s} | {q} | {a} |")

    if acc_mean != "—" and isinstance(acc_mean, float) and acc_mean < 0.75:
        lines += [
            "",
            "> ⚠️ **Quality gate**: `nv_accuracy_mean` is below 0.75 threshold.",
            "> Consider tuning `--top_k`, `--vdb_top_k`, or reviewing corpus quality.",
        ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BAZspark RAG Result Analyzer")
    p.add_argument("--dataset", required=True, help="Dataset label (folder name under results/)")
    p.add_argument("--results-dir", default="results", type=Path, help="Results root directory")
    p.add_argument("--top-n", type=int, default=10, help="Number of worst queries to display")
    p.add_argument("--export-csv", action="store_true", help="Export results to CSV")
    p.add_argument("--markdown", action="store_true", help="Print Markdown report")
    p.add_argument(
        "--save-markdown",
        type=Path,
        default=None,
        help="Save Markdown report to file",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    label = args.dataset
    results_dir = args.results_dir

    print(f"[INFO] Loading results for dataset: {label}")
    data, scores, summary = load_results(results_dir, label)
    print(f"[INFO] {len(data)} rows loaded.")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Summary — {label}")
    print(f"{'='*60}")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Print worst queries table
    print_worst_queries(data, scores, top_n=args.top_n)

    # CSV export
    if args.export_csv:
        csv_path = results_dir / label / f"rag_{label}_eval_export.csv"
        export_csv(data, scores, csv_path)

    # Markdown
    if args.markdown or args.save_markdown:
        md = generate_markdown(data, scores, summary, label, top_n=5)
        if args.markdown:
            print(f"\n{md}\n")
        if args.save_markdown:
            args.save_markdown.write_text(md, encoding="utf-8")
            print(f"[OK] Markdown saved: {args.save_markdown}")


if __name__ == "__main__":
    main()
