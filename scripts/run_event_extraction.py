#!/usr/bin/env python3
"""Create event records using cleaned articles plus entity and temporal outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.event_extractor import EventExtractor
from src.extraction.pipeline_utils import (
    iter_cleaned_articles,
    load_json_by_article,
    write_json_output,
)
from src.utils.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract events from article/entity/temporal inputs."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=settings.abs_path("paths.data_processed")
    )
    parser.add_argument(
        "--entities-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "entities",
    )
    parser.add_argument(
        "--temporals-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "temporals",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "events",
    )
    args = parser.parse_args()

    extractor = EventExtractor()
    entities = load_json_by_article(args.entities_dir)
    temporals = load_json_by_article(args.temporals_dir)
    count = 0
    for article in iter_cleaned_articles(args.input_dir):
        article_id = article["article_id"]
        payload = extractor.extract_article(
            article,
            entities.get(article_id, {"mentions": [], "entities": []}),
            temporals.get(article_id, {"temporal_expressions": []}),
        )
        write_json_output(payload, args.output_dir, article_id, "events")
        count += 1
    print(f"Wrote event outputs for {count} article(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
