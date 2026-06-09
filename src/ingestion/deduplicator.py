"""
temporal_kg.src.ingestion.deduplicator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Prevents re-ingesting articles that are already in the database.

Two dedup strategies are used together:
  1. URL hash  — fast; catches exact URL duplicates even before downloading.
  2. Content hash — catches re-published or cross-posted articles.

The Deduplicator loads the existing hashes from SQLite on first use and
keeps an in-memory set for O(1) lookups during a run.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from src.ingestion.models import ArticleRecord
from src.utils.db import DatabaseManager
from src.utils.logger import get_logger

log = get_logger(__name__)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class Deduplicator:
    """
    In-memory + SQLite deduplication for article URLs and content.

    Parameters
    ----------
    db : DatabaseManager
        Open database connection. Must already have the articles table.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._url_hashes: set[str] = set()
        self._content_hashes: set[str] = set()
        self._loaded = False

    def load(self) -> None:
        """Load existing hashes from the database."""
        rows = self._db.fetchall(
            "SELECT url, content_hash FROM articles WHERE url IS NOT NULL"
        )
        for row in rows:
            url = row.get("url") or ""
            content_hash = row.get("content_hash") or ""
            if url:
                self._url_hashes.add(sha256(url))
            if content_hash:
                self._content_hashes.add(content_hash)

        log.info(
            "Deduplicator loaded: %d URL hashes, %d content hashes",
            len(self._url_hashes),
            len(self._content_hashes),
        )
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def compute_hashes(self, article: ArticleRecord) -> ArticleRecord:
        """
        Compute and assign url_hash and content_hash on *article*.
        Call this after content_clean is set.
        """
        article.url_hash = sha256(article.url) if article.url else ""
        article.content_hash = sha256(article.content_clean) if article.content_clean else ""
        return article

    def is_duplicate(self, article: ArticleRecord) -> tuple[bool, str]:
        """
        Check whether *article* is a duplicate.

        Returns
        -------
        (is_dup, reason)
            reason is a short string describing which check matched.
        """
        self._ensure_loaded()

        if article.url_hash and article.url_hash in self._url_hashes:
            return True, "url_hash"

        if article.content_hash and article.content_hash in self._content_hashes:
            return True, "content_hash"

        return False, ""

    def register(self, article: ArticleRecord) -> None:
        """
        Mark *article* as seen so subsequent checks in this run detect it.
        Call after successful DB insert.
        """
        if article.url_hash:
            self._url_hashes.add(article.url_hash)
        if article.content_hash:
            self._content_hashes.add(article.content_hash)

    @property
    def url_count(self) -> int:
        return len(self._url_hashes)

    @property
    def content_count(self) -> int:
        return len(self._content_hashes)
