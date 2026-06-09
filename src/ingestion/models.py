"""
temporal_kg.src.ingestion.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Data-transfer objects used throughout the ingestion pipeline.
These are plain dataclasses — no ORM, no DB dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ArticleStatus(str, Enum):
    RAW = "raw"
    CLEANED = "cleaned"
    EXTRACTED = "extracted"
    EXPORTED = "exported"
    ERROR = "error"


@dataclass
class FeedConfig:
    """A single RSS/Atom feed as loaded from settings.yaml."""
    name: str
    url: str
    country: str = "general"
    credibility: float = 0.5


@dataclass
class ArticleRecord:
    """
    Full in-memory representation of one article at any pipeline stage.

    Fields
    ------
    url             : canonical article URL (dedup key)
    title           : headline
    source_name     : feed name  (e.g. "Reuters World")
    feed_url        : parent feed URL
    country         : country tag inherited from feed
    published_at    : datetime parsed from RSS or page metadata
    fetched_at      : when we retrieved the page
    content_raw     : raw HTML bytes decoded as str
    content_clean   : HTML-stripped plain text
    language        : detected ISO 639-1 code  (e.g. "en")
    content_hash    : SHA-256 of content_clean (dedup)
    url_hash        : SHA-256 of url (fast dedup)
    is_relevant     : True if China + Romania co-occur
    relevance_reason: short explanation string
    status          : ArticleStatus
    raw_html_path   : relative path where raw HTML was saved
    json_path       : relative path where JSON record was saved
    fetch_error     : last error message, if any
    db_id           : SQLite row id after insertion
    """

    url: str
    title: str = ""
    source_name: str = ""
    feed_url: str = ""
    country: str = ""
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    content_raw: str = ""          # raw HTML
    content_clean: str = ""        # plain text
    language: str = ""
    content_hash: str = ""
    url_hash: str = ""
    is_relevant: bool = False
    relevance_reason: str = ""
    status: ArticleStatus = ArticleStatus.RAW
    raw_html_path: str = ""
    json_path: str = ""
    fetch_error: str = ""
    db_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "url": self.url,
            "title": self.title,
            "source_name": self.source_name,
            "feed_url": self.feed_url,
            "country": self.country,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "content_raw": self.content_raw,
            "content_clean": self.content_clean,
            "language": self.language,
            "content_hash": self.content_hash,
            "url_hash": self.url_hash,
            "is_relevant": self.is_relevant,
            "relevance_reason": self.relevance_reason,
            "status": self.status.value,
            "raw_html_path": self.raw_html_path,
            "json_path": self.json_path,
            "fetch_error": self.fetch_error,
        }


@dataclass
class IngestionRunStats:
    """Counters for one full ingestion run."""
    feed_name: str = ""
    feed_url: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    articles_seen: int = 0
    articles_new: int = 0
    articles_dup: int = 0
    articles_relevant: int = 0
    errors: int = 0
    status: str = "running"   # running | success | failed

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
