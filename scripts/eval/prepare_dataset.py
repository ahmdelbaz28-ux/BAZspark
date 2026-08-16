#!/usr/bin/env python3
r"""
prepare_dataset.py — BAZspark RAG Evaluation Dataset Preparer
=============================================================
Converts engineering data from various source formats (CSV, JSONL, JSON)
into the rag-eval corpus/ + train.json layout.

Also validates existing train.json files for conformance.

Usage:
  # Validate existing dataset
  python scripts/eval/prepare_dataset.py --validate eval/nfpa72_rag_dataset

  # Convert JSONL to train.json
  python scripts/eval/prepare_dataset.py \\
    --from-jsonl source.jsonl \\
    --output-dir eval/my_new_dataset

  # Convert CSV to train.json
  python scripts/eval/prepare_dataset.py \\
    --from-csv source.csv \\
    --question-col question --answer-col answer \\
    --output-dir eval/my_new_dataset

Run from the REPO ROOT.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────


def validate_dataset(dataset_path: Path) -> bool:
    """
    Validate corpus/ + train.json layout per rag-eval dataset-and-conversion.md spec.
    Returns True if valid, prints errors and returns False otherwise.
    """
    ok = True

    # Check corpus directory
    corpus_dir = dataset_path / "corpus"
    if not corpus_dir.exists():
        print(f"[ERROR] corpus/ directory not found in {dataset_path}")
        ok = False
    else:
        corpus_files = list(corpus_dir.glob("**/*"))
        corpus_files = [f for f in corpus_files if f.is_file()]
        print(f"[OK]   corpus/ found with {len(corpus_files)} file(s)")
        for cf in corpus_files:
            print(f"       - {cf.name}")

    # Check train.json
    train_file = dataset_path / "train.json"
    if not train_file.exists():
        print(f"[ERROR] train.json not found in {dataset_path}")
        return False

    try:
        with open(train_file, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] train.json is not valid JSON: {e}")
        return False

    if not isinstance(data, list):
        print(f"[ERROR] train.json must be a top-level JSON array, got {type(data).__name__}")
        ok = False
    elif not all(isinstance(r, dict) for r in data):
        print("[ERROR] train.json items must be objects (dicts)")
        ok = False
    else:
        print(f"[OK]   train.json is a valid array with {len(data)} row(s)")

        # Check required fields
        missing_q = [i for i, r in enumerate(data) if "question" not in r]
        missing_a = [i for i, r in enumerate(data) if "answer" not in r]
        if missing_q:
            print(f"[ERROR] Rows missing 'question': {missing_q[:10]}")
            ok = False
        if missing_a:
            print(f"[ERROR] Rows missing 'answer': {missing_a[:10]}")
            ok = False

        # Check id type (must be integer or absent)
        bad_ids = [i for i, r in enumerate(data) if "id" in r and not isinstance(r["id"], int)]
        if bad_ids:
            print(
                f"[WARN]  Rows with non-integer 'id': {bad_ids[:10]} (use integer from row index)"
            )

        # Check contexts filenames exist in corpus
        if corpus_dir.exists():
            corpus_basenames = {f.name for f in corpus_dir.glob("**/*") if f.is_file()}
            for i, row in enumerate(data):
                for ctx in row.get("contexts", []):
                    if isinstance(ctx, dict) and "filename" in ctx:
                        if ctx["filename"] not in corpus_basenames:
                            print(
                                f"[WARN]  Row {i}: context filename '{ctx['filename']}' "
                                f"not found in corpus/"
                            )
        if ok:
            print("[OK]   All required fields present. Dataset is valid.")

    return ok


# ──────────────────────────────────────────────────────────────────────────────
# Conversion: JSONL → train.json
# ──────────────────────────────────────────────────────────────────────────────


def convert_jsonl(
    source: Path,
    output_dir: Path,
    question_col: str = "question",
    answer_col: str = "answer",
) -> None:
    """Convert a JSONL file to train.json format."""
    rows = []
    with open(source, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    train: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        entry: dict[str, Any] = {
            "id": r.get("id", i) if isinstance(r.get("id"), int) else i,
            "question": r[question_col],
            "answer": r[answer_col],
            "is_impossible": r.get("is_impossible", False),
        }
        if "contexts" in r:
            entry["contexts"] = r["contexts"]
        train.append(entry)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "train.json"
    out_file.write_text(json.dumps(train, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Wrote {len(train)} rows to {out_file}")


# ──────────────────────────────────────────────────────────────────────────────
# Conversion: CSV → train.json
# ──────────────────────────────────────────────────────────────────────────────


def convert_csv(
    source: Path,
    output_dir: Path,
    question_col: str = "question",
    answer_col: str = "answer",
) -> None:
    """Convert a CSV file to train.json format."""
    with open(source, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    train: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        if question_col not in r or answer_col not in r:
            raise ValueError(
                f"CSV must contain columns '{question_col}' and '{answer_col}'. "
                f"Found: {list(r.keys())}"
            )
        entry: dict[str, Any] = {
            "id": i,
            "question": r[question_col].strip(),
            "answer": r[answer_col].strip(),
            "is_impossible": False,
        }
        train.append(entry)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "train.json"
    out_file.write_text(json.dumps(train, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Wrote {len(train)} rows to {out_file}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BAZspark RAG Eval Dataset Preparer & Validator")
    sub = p.add_subparsers(dest="command")

    # validate command
    val = sub.add_parser("validate", help="Validate an existing dataset directory")
    val.add_argument(
        "dataset_path", type=Path, help="Path to dataset root (contains corpus/ and train.json)"
    )

    # from-jsonl command
    jl = sub.add_parser("from-jsonl", help="Convert JSONL source to train.json")
    jl.add_argument("source", type=Path, help="Source JSONL file")
    jl.add_argument("--output-dir", type=Path, required=True, help="Output dataset root directory")
    jl.add_argument("--question-col", default="question")
    jl.add_argument("--answer-col", default="answer")

    # from-csv command
    cv = sub.add_parser("from-csv", help="Convert CSV source to train.json")
    cv.add_argument("source", type=Path, help="Source CSV file")
    cv.add_argument("--output-dir", type=Path, required=True, help="Output dataset root directory")
    cv.add_argument("--question-col", default="question")
    cv.add_argument("--answer-col", default="answer")

    # Legacy: --validate flag for backwards compat
    p.add_argument(
        "--validate",
        type=Path,
        metavar="DATASET_PATH",
        help="(Legacy) Validate dataset at given path",
    )

    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Legacy --validate flag
    if hasattr(args, "validate") and args.validate and not args.command:
        ok = validate_dataset(args.validate)
        sys.exit(0 if ok else 1)

    if not args.command:
        print("Usage: python scripts/eval/prepare_dataset.py <command> [options]")
        print("Commands: validate, from-jsonl, from-csv")
        print("Or: python scripts/eval/prepare_dataset.py --validate <path>")
        sys.exit(1)

    if args.command == "validate":
        ok = validate_dataset(args.dataset_path)
        sys.exit(0 if ok else 1)

    elif args.command == "from-jsonl":
        convert_jsonl(args.source, args.output_dir, args.question_col, args.answer_col)

    elif args.command == "from-csv":
        convert_csv(args.source, args.output_dir, args.question_col, args.answer_col)


if __name__ == "__main__":
    main()
