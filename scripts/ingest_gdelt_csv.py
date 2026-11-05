#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Ingest a BigQuery GKG export (see gdelt_bigquery.sql) through the normal
scrape -> translate -> relevance -> persist pipeline.

    python scripts/ingest_gdelt_csv.py data/raw/gdelt_bq.csv [--limit 200]
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.gdelt_fetcher import _parse_seendate  # noqa: E402
from src.ingestion.models import ArticleRecord, FeedConfig  # noqa: E402
from src.ingestion.pipeline import IngestionPipeline  # noqa: E402

_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def load_stubs(path: Path, limit: int | None, skip: int = 0) -> list[ArticleRecord]:
    stubs, seen = [], set()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            url = (row.get("url") or "").strip()
            if not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            if len(seen) <= skip:
                continue
            domain = (row.get("domain") or "").strip()
            stubs.append(ArticleRecord(
                url=url,
                title=html.unescape(row.get("title") or "").strip(),
                source_name=f"GDELT:{domain}" if domain else "GDELT",
                feed_url=_URL,
                country="unknown",
                # GKG DATE is YYYYMMDDHHMMSS; reuse the fetcher's parser on the date part
                published_at=_parse_seendate((row.get("date") or "")[:8]),
            ))
            if limit and len(stubs) >= limit:
                break
    return stubs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--limit", type=int, default=None, help="cap stubs (try 200 first)")
    ap.add_argument("--skip", type=int, default=0, help="skip the first N unique URLs")
    args = ap.parse_args()

    stubs = load_stubs(args.csv, args.limit, args.skip)
    assert stubs, f"no usable rows in {args.csv}"
    print(f"{len(stubs)} unique URLs")
    feed = FeedConfig(name="GDELT China-Romania", url=_URL, country="bilateral", credibility=0.7)
    stats = IngestionPipeline().run_feed(feed, preloaded_stubs=stubs)
    print(f"new={stats.articles_new} dup={stats.articles_dup} relevant={stats.articles_relevant} errors={stats.errors}")


if __name__ == "__main__":
    main()
