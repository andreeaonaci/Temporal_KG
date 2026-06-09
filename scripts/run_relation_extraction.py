#!/usr/bin/env python3
"""Create relation records using cleaned articles and extracted layers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.pipeline_utils import (
    iter_cleaned_articles,
    load_json_by_article,
    write_json_output,
)
from src.extraction.relation_extractor import RelationExtractor
from src.utils.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract relations from cleaned articles and extracted layers."
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
        "--events-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "events",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "relations",
    )
    args = parser.parse_args()

    extractor = RelationExtractor()
    entities = load_json_by_article(args.entities_dir)
    temporals = load_json_by_article(args.temporals_dir)
    events = load_json_by_article(args.events_dir)
    count = 0
    for article in iter_cleaned_articles(args.input_dir):
        article_id = article["article_id"]
        payload = extractor.extract_article(
            article,
            entities.get(article_id, {"mentions": [], "entities": []}),
            temporals.get(article_id, {"temporal_expressions": []}),
            events.get(article_id, {"events": []}),
        )
        write_json_output(payload, args.output_dir, article_id, "relations")
        count += 1
    print(f"Wrote relation outputs for {count} article(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
