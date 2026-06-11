#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

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
