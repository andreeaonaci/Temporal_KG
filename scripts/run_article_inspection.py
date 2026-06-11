#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Inspect recent SQLite articles from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.helpers import load_sqlite_articles  # noqa: E402
from src.utils.config import settings  # noqa: E402


DEFAULT_COLUMNS = [
    "published_at",
    "source_name",
    "title",
    "is_relevant",
    "relevance_reason",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load recent articles and print an inspection table."
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=settings.abs_path("database.sqlite_path"),
        help="Path to SQLite database.",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Optional CSV output path.",
    )
    args = parser.parse_args()

    frame = load_sqlite_articles(sqlite_path=args.sqlite_path, limit=args.limit)
    if frame.empty:
        print("No articles found.")
        return

    visible_cols = [col for col in DEFAULT_COLUMNS if col in frame.columns]
    print(frame[visible_cols].to_string(index=False))

    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output_csv, index=False)
        print(f"Wrote {len(frame)} row(s) to {args.output_csv}")


if __name__ == "__main__":
    main()
