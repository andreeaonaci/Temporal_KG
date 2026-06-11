#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
Backfill translation for already-ingested non-English articles.

Usage:
  python scripts/backfill_translation.py
  python scripts/backfill_translation.py --limit 200
  python scripts/backfill_translation.py --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.models import ArticleRecord
from src.ingestion.translator import Translator
from src.utils.config import settings


def iter_candidates(cur: sqlite3.Cursor, limit: int | None):
    sql = """
    SELECT id, url, COALESCE(title, '') AS title, COALESCE(content_clean, '') AS content_clean,
           COALESCE(language, 'unknown') AS language,
           COALESCE(relevance_reason, '') AS relevance_reason
    FROM articles
        WHERE (COALESCE(content_clean, '') <> '' OR COALESCE(title, '') <> '')
      AND LOWER(COALESCE(language, 'unknown')) <> 'en'
      AND COALESCE(relevance_reason, '') NOT LIKE '%translated_from_%'
    ORDER BY id ASC
    """
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"
    return cur.execute(sql)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill translations for existing articles")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Show candidate count only")
    args = parser.parse_args()

    db_path = PROJECT_ROOT / settings("paths.db", "db/temporal_kg.sqlite")
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = list(iter_candidates(cur, args.limit if args.limit > 0 else None))
    print(f"Candidates: {len(rows)}")
    if args.dry_run:
        con.close()
        return 0

    translator = Translator()
    ok = 0
    failed = 0

    for row in rows:
        art = ArticleRecord(
            url=row["url"],
            title=row["title"],
            content_clean=row["content_clean"],
            language=row["language"],
            relevance_reason=row["relevance_reason"],
        )

        try:
            translator.translate(art)
            cur.execute(
                """
                UPDATE articles
                SET title = ?,
                    content_clean = ?,
                    relevance_reason = ?,
                    language = ?
                WHERE id = ?
                """,
                (art.title, art.content_clean, art.relevance_reason, art.language, row["id"]),
            )
            ok += 1
        except Exception as exc:
            failed += 1
            cur.execute(
                """
                UPDATE articles
                SET fetch_error = ?
                WHERE id = ?
                """,
                (f"translation_backfill_failed: {exc}", row["id"]),
            )

    con.commit()
    con.close()

    print(f"Translated: {ok}")
    print(f"Failed: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
