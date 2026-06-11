#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Analyze exported entity rows from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.helpers import chart_source_activity, load_json_exports  # noqa: E402
from src.utils.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize entity exports by source."
    )
    parser.add_argument(
        "--entities-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "entities",
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output-csv", type=Path, help="Optional CSV output path.")
    args = parser.parse_args()

    frame = load_json_exports(args.entities_dir)
    if frame.empty:
        print(f"No entity exports found in {args.entities_dir}")
        return

    counts = chart_source_activity(frame.fillna({"source_name": "unknown"})).head(args.top)
    print(counts.to_string())

    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        counts.rename_axis("source_name").reset_index(name="entity_rows").to_csv(
            args.output_csv, index=False
        )
        print(f"Wrote source counts to {args.output_csv}")


if __name__ == "__main__":
    main()
