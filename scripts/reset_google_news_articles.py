#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""One-time reset for Google-News-sourced articles ingested before the
wrapper-URL resolver (src/ingestion/google_news_resolver.py) existed.

Those rows are stuck: re-running ingestion resolves their URL correctly now,
but content-hash deduplication (matching on title+snippet, not URL) still
recognizes them as "the same article already ingested" and skips them --
so the *old* wrapper-URL row, and everything extracted from it
(data/processed JSON, data/exports/{entities,temporals,events,relations}),
never gets replaced by a fresh, resolved-URL version no matter how many
times ingestion re-runs.

This isn't a patch-in-place: url_hash (the article_id used to key every
downstream export file) is derived from the URL, so a resolved URL means a
*different* article_id -- trying to rewrite the old rows/files in place
would leave stale, mismatched ids scattered across every export directory.
Deleting the old rows/files instead and letting a normal ingestion re-run
insert them fresh (with correct resolved-URL-based ids flowing consistently
through the whole pipeline) is safer and simpler than reconciling that by
hand.

Only touches rows whose URL is still the unresolved
`https://news.google.com/...` wrapper -- anything already resolved (or
never a Google News URL) is left untouched.

Usage:
    python scripts/reset_google_news_articles.py            # dry run, reports what it would delete
    python scripts/reset_google_news_articles.py --confirm  # actually deletes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import settings  # noqa: E402
from src.utils.db import get_db  # noqa: E402

EXPORT_STEMS = ("entities", "temporals", "events", "relations")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete already-ingested Google-News wrapper-URL articles so a "
        "fresh ingestion run re-adds them with resolved publisher URLs."
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Actually delete. Without this flag, only reports what would be deleted.",
    )
    args = parser.parse_args()

    db = get_db()
    db.connect()
    try:
        rows = db.fetchall(
            "SELECT id, url, json_path, content_hash_url FROM articles "
            "WHERE url LIKE 'https://news.google.com/%'"
        )
    finally:
        if not args.confirm:
            db.close()

    if not rows:
        print("No unresolved Google News wrapper-URL articles found -- nothing to reset.")
        return

    print(f"Found {len(rows)} unresolved Google News article(s){'':s}:")
    exports_root = settings.abs_path("paths.data_exports")
    files_to_delete: list[Path] = []
    for row in rows:
        print(f"  [{row['id']}] {row['url'][:90]}")
        if row["json_path"]:
            files_to_delete.append(PROJECT_ROOT / row["json_path"])
        article_id = row["content_hash_url"]
        if article_id:
            for stem in EXPORT_STEMS:
                candidate = exports_root / stem / f"{article_id}.{stem}.json"
                if candidate.exists():
                    files_to_delete.append(candidate)

    print(f"\n{len(files_to_delete)} export file(s) also matched for deletion.")

    if not args.confirm:
        print(
            "\nDry run only -- nothing deleted. Re-run with --confirm to actually delete, "
            "then run: python scripts/run_ingestion.py --sources rss"
        )
        return

    try:
        db.execute(
            "DELETE FROM articles WHERE url LIKE 'https://news.google.com/%'"
        )
        db.commit()
        deleted_files = 0
        for path in files_to_delete:
            try:
                path.unlink()
                deleted_files += 1
            except FileNotFoundError:
                pass
        print(
            f"Deleted {len(rows)} DB row(s) and {deleted_files} export file(s). "
            "Run `python scripts/run_ingestion.py --sources rss` now to re-ingest "
            "them with resolved URLs, then re-run extraction/corroboration/veracity."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
