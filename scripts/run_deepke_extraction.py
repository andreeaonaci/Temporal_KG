#!/usr/bin/env python3
"""Run DeepKE over cleaned articles and store normalized outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.deepke_client import DeepKEClient  # noqa: E402
from src.extraction.pipeline_utils import iter_cleaned_articles  # noqa: E402
from src.utils.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DeepKE extraction.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=settings.abs_path("paths.data_processed"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.abs_path("extraction.deepke.output_dir"),
    )
    parser.add_argument(
        "--input-cache",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "deepke" / "inputs",
    )
    args = parser.parse_args()

    client = DeepKEClient()
    if not client.enabled():
        raise SystemExit("DeepKE is disabled in settings. Set extraction.deepke.enabled=true.")

    count = 0
    for article in iter_cleaned_articles(args.input_dir):
        article_id = article.get("article_id")
        if not article_id:
            continue
        input_path = client.write_input(article, args.input_cache)
        output_path = args.output_dir / f"{article_id}.json"
        ok = client.run(input_path, output_path)
        if ok:
            count += 1
    print(f"DeepKE outputs written for {count} article(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
