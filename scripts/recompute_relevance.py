#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Recompute relevance flags for already stored articles.

Useful after changing relevance terms or relevance.mode.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.models import ArticleRecord
from src.ingestion.relevance_filter import RelevanceFilter

DB_PATH = PROJECT_ROOT / "db" / "temporal_kg.sqlite"


def main() -> int:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = list(
        cur.execute(
            """
            SELECT id, url, COALESCE(title, '') AS title,
                   COALESCE(content_clean, '') AS content_clean,
                   COALESCE(country, '') AS country
            FROM articles
            ORDER BY id ASC
            """
        )
    )

    filt = RelevanceFilter()
    updated = 0

    for row in rows:
        art = ArticleRecord(
            url=row["url"],
            title=row["title"],
            content_clean=row["content_clean"],
            country=row["country"],
        )
        filt.check(art)

        cur.execute(
            """
            UPDATE articles
            SET is_relevant = ?,
                relevance_reason = ?
            WHERE id = ?
            """,
            (1 if art.is_relevant else 0, art.relevance_reason, row["id"]),
        )
        updated += 1

    con.commit()

    total_rel = cur.execute(
        "SELECT COUNT(1) FROM articles WHERE is_relevant = 1"
    ).fetchone()[0]
    con.close()

    print(f"rows_recomputed={updated}")
    print(f"relevant_total={total_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
