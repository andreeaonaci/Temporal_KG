"""
temporal_kg.src.ingestion.article_store
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Persists ArticleRecord objects to:
  1. SQLite (metadata + text fields)
  2. JSON files under data/processed/<date>/<url_hash>.json

The store is responsible for all DB writes in the ingestion pipeline.
It never reads — that is the deduplicator's job.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.ingestion.models import ArticleRecord, ArticleStatus, IngestionRunStats
from src.utils.config import settings
from src.utils.db import DatabaseManager
from src.utils.logger import get_logger

log = get_logger(__name__)


def _json_path(article: ArticleRecord, base_dir: Path) -> Path:
    """Deterministic JSON save path: data/processed/YYYY-MM-DD/<url_hash[:16]>.json"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fname = (article.url_hash or "unknown")[:16] + ".json"
    dest = base_dir / today
    dest.mkdir(parents=True, exist_ok=True)
    return dest / fname


class ArticleStore:
    """
    Write-only facade for article persistence.

    Parameters
    ----------
    db : DatabaseManager
        Open DB connection.
    save_json : bool
        Whether to write JSON files to data/processed/.
    processed_dir : Path | None
        Override default processed-data directory.
    """

    def __init__(
        self,
        db: DatabaseManager,
        save_json: bool | None = None,
        processed_dir: Path | None = None,
    ) -> None:
        self._db = db
        self._save_json = (
            save_json
            if save_json is not None
            else settings("ingestion.save_json", True)
        )
        self._proc_dir = processed_dir or settings.abs_path("paths.data_processed")
        self._proc_dir.mkdir(parents=True, exist_ok=True)

    # ── Feed registry ─────────────────────────────────────────────────────────

    def upsert_feed(self, name: str, url: str, country: str, credibility: float) -> int:
        """
        Insert a feed row if it doesn't exist; return its id.
        """
        existing = self._db.fetchone("SELECT id FROM feeds WHERE url = ?", (url,))
        if existing:
            return existing["id"]

        cur = self._db.execute(
            """
            INSERT INTO feeds (name, url, country, credibility)
            VALUES (?, ?, ?, ?)
            """,
            (name, url, country, credibility),
        )
        self._db.commit()
        return cur.lastrowid

    def update_feed_cache(
        self, feed_id: int, etag: Optional[str], last_modified: Optional[str]
    ) -> None:
        self._db.execute(
            """
            UPDATE feeds
            SET last_fetched_at = datetime('now'),
                last_etag = ?,
                last_modified = ?
            WHERE id = ?
            """,
            (etag, last_modified, feed_id),
        )
        self._db.commit()

    def increment_feed_article_count(self, feed_id: int, count: int) -> None:
        self._db.execute(
            "UPDATE feeds SET articles_total = articles_total + ? WHERE id = ?",
            (count, feed_id),
        )
        self._db.commit()

    # ── Ingestion run ─────────────────────────────────────────────────────────

    def start_run(self, feed_id: int, feed_url: str) -> int:
        """Insert a new ingestion_runs row; return its id."""
        cur = self._db.execute(
            """
            INSERT INTO ingestion_runs (feed_id, feed_url, started_at, status)
            VALUES (?, ?, datetime('now'), 'running')
            """,
            (feed_id, feed_url),
        )
        self._db.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, stats: IngestionRunStats) -> None:
        self._db.execute(
            """
            UPDATE ingestion_runs
            SET finished_at = datetime('now'),
                articles_new = ?,
                articles_dup = ?,
                articles_relevant = ?,
                errors = ?,
                status = ?
            WHERE id = ?
            """,
            (
                stats.articles_new,
                stats.articles_dup,
                stats.articles_relevant,
                stats.errors,
                stats.status,
                run_id,
            ),
        )
        self._db.commit()

    # ── Article persistence ───────────────────────────────────────────────────

    def save_article(self, article: ArticleRecord) -> Optional[int]:
        """
        Persist *article* to SQLite and (optionally) to a JSON file.

        Returns the new SQLite row id, or None on failure.
        """
        # ── JSON file ─────────────────────────────────────────────────────────
        if self._save_json:
            try:
                dest = _json_path(article, self._proc_dir)
                dest.write_text(
                    json.dumps(article.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                try:
                    display_path = dest.relative_to(settings.project_root)
                except ValueError:
                    display_path = dest
                article.json_path = str(display_path)
                log.debug("JSON saved: %s", display_path)
            except OSError as exc:
                log.warning("Could not save JSON: %s", exc)

        # ── SQLite row ────────────────────────────────────────────────────────
        try:
            cur = self._db.execute(
                """
                INSERT INTO articles (
                    url, title, content_raw, content_clean,
                    language, country,
                    published_at, fetched_at, status,
                    content_hash, content_hash_url,
                    is_relevant, relevance_reason,
                    raw_html_path, json_path,
                    language_detected, fetch_error,
                    credibility
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?
                )
                """,
                (
                    article.url,
                    article.title,
                    article.content_raw,
                    article.content_clean,
                    article.language,
                    article.country,
                    article.published_at.isoformat() if article.published_at else None,
                    article.fetched_at.isoformat() if article.fetched_at else None,
                    article.status.value,
                    article.content_hash,
                    article.url_hash,
                    1 if article.is_relevant else 0,
                    article.relevance_reason,
                    article.raw_html_path,
                    article.json_path,
                    article.language,
                    article.fetch_error,
                    None,  # credibility — set by scorer in a later phase
                ),
            )
            self._db.commit()
            article.db_id = cur.lastrowid
            log.debug("Article saved (id=%d): %s", article.db_id, article.url[:80])
            return article.db_id

        except Exception as exc:
            log.error("DB insert failed for %s: %s", article.url, exc)
            self._db.rollback()
            return None
