# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.rss_fetcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetches China-Romania article stubs from configured RSS/Atom feeds.

Mirrors GdeltFetcher's role exactly (see gdelt_fetcher.py): converts raw
feed entries into ArticleRecord stubs with title/content_clean populated
from the feed's own summary field, no separate article-page download --
IngestionPipeline._process_article() already treats "GDELT-only" text
prep generically (title + whatever content_clean the stub arrived with),
so RSS stubs flow through the exact same pipeline unchanged.

This is real, previously-undelivered functionality: docs/REQUIREMENTS_MAPPING.md
has claimed "RSS feed integration" as complete since this project's first
commit, citing this exact file path and an `ingestion.rss_feeds` config
block that did not exist until now.
"""

from __future__ import annotations

from src.ingestion import google_news_resolver
from src.ingestion.feed_parser import parse_feed
from src.ingestion.models import ArticleRecord, FeedConfig
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def load_configured_feeds() -> list[FeedConfig]:
    """Build FeedConfig objects from settings.yaml's ingestion.rss_feeds list."""
    raw_feeds = settings("ingestion.rss_feeds", [])
    feeds: list[FeedConfig] = []
    for entry in raw_feeds:
        feeds.append(
            FeedConfig(
                name=entry["name"],
                url=entry["url"],
                country=entry.get("country", "general"),
                credibility=float(entry.get("credibility", 0.5)),
            )
        )
    return feeds


class RssFetcher:
    """Fetches and converts RSS/Atom feed entries into ArticleRecord stubs."""

    def fetch_feed(self, feed_cfg: FeedConfig) -> list[ArticleRecord]:
        entries = parse_feed(feed_cfg.url)
        log.info("Feed '%s': %d raw entries", feed_cfg.name, len(entries))

        wrapper_count = sum(1 for e in entries if google_news_resolver.is_google_news_wrapper(e["link"]))
        if wrapper_count:
            log.info(
                "Feed '%s': resolving %d Google News wrapper URL(s) to real "
                "publisher URLs (one network round-trip each)...",
                feed_cfg.name,
                wrapper_count,
            )

        stubs = []
        for entry in entries:
            resolved_link = google_news_resolver.resolve(entry["link"])
            stubs.append(self._to_stub(entry, feed_cfg, resolved_link))
        return stubs

    @staticmethod
    def _to_stub(entry: dict, feed_cfg: FeedConfig, resolved_link: str) -> ArticleRecord:
        return ArticleRecord(
            url=resolved_link,
            title=entry["title"],
            source_name=feed_cfg.name,
            feed_url=feed_cfg.url,
            country=feed_cfg.country,
            published_at=entry["published"],
            content_clean=entry["summary"],
        )
