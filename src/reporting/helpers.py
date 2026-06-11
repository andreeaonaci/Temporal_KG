# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Notebook-friendly loading and chart helper functions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from src.extraction.pipeline_utils import load_json_by_article
from src.utils.config import settings
from src.utils.db import DatabaseManager


def load_sqlite_articles(
    sqlite_path: Path | None = None,
    *,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load article rows from SQLite into a dataframe."""
    db_path = sqlite_path or settings.abs_path("database.sqlite_path")
    query = (
        "SELECT a.id, a.url, a.title, s.name AS source_name, a.country, a.published_at, "
        "a.language, a.is_relevant, a.relevance_reason, a.status "
        "FROM articles a LEFT JOIN sources s ON a.source_id = s.id "
        "ORDER BY a.published_at DESC"
    )
    if limit:
        query += f" LIMIT {int(limit)}"
    with DatabaseManager(db_path) as db:
        rows = [dict(row) for row in db.fetchall(query)]
    return pd.DataFrame(rows)


def load_json_exports(directory: Path) -> pd.DataFrame:
    """Load article-keyed JSON exports into a flat dataframe."""
    rows = []
    for article_id, payload in load_json_by_article(directory).items():
        rows.append({"article_id": article_id, **payload})
    return pd.DataFrame(rows)


def chart_volume_over_time(
    rows: pd.DataFrame,
    *,
    date_column: str = "published_at",
    freq: str = "ME",
) -> pd.Series:
    """Return a plotting-ready count series over time."""
    frame = rows.copy()
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame = frame.dropna(subset=[date_column])
    return frame.set_index(date_column).resample(freq).size()


def chart_source_activity(
    rows: pd.DataFrame,
    *,
    source_column: str = "source_name",
) -> pd.Series:
    """Return source activity counts for bar charts."""
    if source_column not in rows:
        return pd.Series(dtype="int64")
    return rows[source_column].fillna("unknown").value_counts()


def chart_event_type_distribution(events: list[dict[str, Any]]) -> pd.Series:
    """Return event-type counts for plotting."""
    counts = Counter(event.get("event_type") for event in events)
    return pd.Series(counts).sort_values(ascending=False)
