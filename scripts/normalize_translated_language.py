#!/usr/bin/env python3
"""Normalize language to 'en' for rows already marked as translated."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "temporal_kg.sqlite"

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute(
    """
    UPDATE articles
    SET language = 'en'
    WHERE COALESCE(relevance_reason, '') LIKE '%translated_from_%'
      AND LOWER(COALESCE(language, '')) <> 'en'
    """
)
print(f"rows_updated={cur.rowcount}")
con.commit()
con.close()
