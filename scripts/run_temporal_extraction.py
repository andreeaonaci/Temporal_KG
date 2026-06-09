#!/usr/bin/env python3
"""Process cleaned articles and write temporal extraction outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.pipeline_utils import iter_cleaned_articles, write_json_output
from src.temporal.temporal_extractor import TemporalExtractor
from src.utils.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract temporal expressions from cleaned article JSON files."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=settings.abs_path("paths.data_processed")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "temporals",
    )
    parser.add_argument(
        "--engine",
        choices=["regex", "heideltime"],
        help="Override temporal engine for this run.",
    )
    args = parser.parse_args()

    if args.engine:
        settings._cfg.setdefault("temporal", {})["engine"] = args.engine

    extractor = TemporalExtractor()
    count = 0
    for article in iter_cleaned_articles(args.input_dir):
        payload = extractor.extract_article(article)
        write_json_output(payload, args.output_dir, payload["article_id"], "temporals")
        count += 1
    print(f"Wrote temporal outputs for {count} article(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
