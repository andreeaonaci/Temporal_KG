#!/usr/bin/env python3
"""Run quick project/database/feed exploration from the command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.rss_fetcher import RssFetcher  # noqa: E402
from src.utils.config import settings  # noqa: E402
from src.utils.db import get_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show project config, DB tables, and optional RSS preview."
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=3,
        help="Number of fetched article titles to print (default: 3).",
    )
    parser.add_argument(
        "--skip-feed-preview",
        action="store_true",
        help="Skip RSS fetch preview.",
    )
    args = parser.parse_args()

    print(f"Project root: {settings.project_root}")
    print(f"Project name: {settings('project.name')}")

    with get_db() as db:
        tables = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    print("Tables:", [row["name"] for row in tables])

    if args.skip_feed_preview:
        return

    fetcher = RssFetcher()
    articles = list(fetcher.fetch())
    print(f"Fetched {len(articles)} article(s)")
    for article in articles[: max(args.preview_count, 0)]:
        print(f" - {article.title[:120]}")


if __name__ == "__main__":
    main()
