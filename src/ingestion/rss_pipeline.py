# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.rss_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
High-level orchestrator for RSS-based ingestion -- the RSS-side twin of
gdelt_pipeline.py. Reads every configured feed in ingestion.rss_feeds,
fetches its entries, and runs each feed's stubs through the same
IngestionPipeline used for GDELT (language-detect, translate,
relevance-check, persist).

Usage
-----
    from src.ingestion.rss_pipeline import RssIngestionPipeline

    pipeline = RssIngestionPipeline()
    all_stats = pipeline.run()   # one IngestionRunStats per configured feed
"""

from __future__ import annotations

from typing import Optional

from src.ingestion.models import FeedConfig, IngestionRunStats
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.rss_fetcher import RssFetcher, load_configured_feeds
from src.utils.db import DatabaseManager
from src.utils.logger import get_logger

log = get_logger(__name__)


class RssIngestionPipeline:
    """Orchestrates ingestion across every configured RSS/Atom feed."""

    def __init__(
        self,
        show_progress: bool = True,
        fetcher: RssFetcher | None = None,
        db: Optional[DatabaseManager] = None,
    ) -> None:
        self._fetcher = fetcher or RssFetcher()
        self._pipeline = IngestionPipeline(db=db, show_progress=show_progress)

    def run(self, feeds: list[FeedConfig] | None = None) -> list[IngestionRunStats]:
        feeds = feeds if feeds is not None else load_configured_feeds()
        if not feeds:
            log.warning(
                "No RSS feeds configured (ingestion.rss_feeds is empty) -- nothing to do."
            )
            return []

        all_stats: list[IngestionRunStats] = []
        for feed_cfg in feeds:
            log.info("RSS ingestion starting for feed '%s' (%s)", feed_cfg.name, feed_cfg.url)
            try:
                stubs = self._fetcher.fetch_feed(feed_cfg)
            except Exception as exc:
                log.error("Failed to fetch feed '%s': %s", feed_cfg.name, exc)
                all_stats.append(
                    IngestionRunStats(
                        feed_name=feed_cfg.name, feed_url=feed_cfg.url, status="failed", errors=1
                    )
                )
                continue

            if not stubs:
                log.warning("Feed '%s' returned no entries.", feed_cfg.name)

            stats = self._pipeline.run_feed(feed_cfg, preloaded_stubs=stubs)
            all_stats.append(stats)
        return all_stats
