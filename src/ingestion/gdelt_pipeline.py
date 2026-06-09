"""
temporal_kg.src.ingestion.gdelt_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
High-level orchestrator for GDELT-based ingestion.

Instead of parsing RSS feeds, this pipeline:
  1. Queries the GDELT 2.0 Full-Text Search API for China–Romania articles.
  2. Converts the API results into ArticleRecord stubs.
    3. Passes the stubs through the GDELT-only IngestionPipeline
         (language-detect, translate, relevance-check, persist).

Usage
-----
    from src.ingestion.gdelt_pipeline import GdeltIngestionPipeline

    pipeline = GdeltIngestionPipeline()
    stats = pipeline.run(timespan="24hours")
    print(stats.articles_new, "new GDELT articles ingested")
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.ingestion.gdelt_fetcher import GdeltFetcher
from src.ingestion.models import FeedConfig, IngestionRunStats
from src.ingestion.pipeline import IngestionPipeline
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_GDELT_FEED_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


class GdeltIngestionPipeline:
    """
    Orchestrates GDELT-based article ingestion.

    Parameters
    ----------
    query : str | None
        Override the GDELT search query (default from ``settings.gdelt.query``).
    show_progress : bool
        Display tqdm progress bars.
    """

    def __init__(
        self,
        query: str | None = None,
        show_progress: bool = True,
    ) -> None:
        self._query: str = query or settings("gdelt.query", "China Romania")
        self._default_credibility: float = float(
            settings("gdelt.default_credibility", 0.7)
        )
        self._fetcher = GdeltFetcher(query=self._query)
        self._pipeline = IngestionPipeline(show_progress=show_progress)

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(
        self,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        timespan: str | None = None,
        max_records: int | None = None,
    ) -> IngestionRunStats:
        """
        Fetch articles from GDELT and ingest them through the standard pipeline.

        Supply either *start_date* / *end_date* **or** *timespan* (not both).
        When none are given the configured ``gdelt.default_timespan`` is used.

        Parameters
        ----------
        start_date : datetime | None
            Inclusive range start (UTC).
        end_date : datetime | None
            Inclusive range end (UTC).
        timespan : str | None
            GDELT timespan string, e.g. ``"24hours"``, ``"1week"``.
        max_records : int | None
            Override the configured GDELT max_records cap (1–250).

        Returns
        -------
        IngestionRunStats
            Summary statistics for this GDELT ingestion run.
        """
        log.info("=" * 60)
        log.info("GDELT ingestion pipeline starting (query=%r)", self._query)
        log.info("=" * 60)

        # ── Step 1: fetch stubs from GDELT ────────────────────────────────────
        stubs = self._fetcher.fetch(
            start_date=start_date,
            end_date=end_date,
            timespan=timespan,
            max_records=max_records,
        )

        if not stubs:
            log.warning("GDELT returned no articles for query %r.", self._query)
            return IngestionRunStats(
                feed_name="GDELT China-Romania",
                feed_url=_GDELT_FEED_URL,
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
                status="success",
            )

        log.info("GDELT stubs fetched: %d", len(stubs))

        # ── Step 2: run stubs through the standard pipeline ───────────────────
        gdelt_feed = FeedConfig(
            name="GDELT China-Romania",
            url=_GDELT_FEED_URL,
            country="bilateral",
            credibility=self._default_credibility,
        )

        stats = self._pipeline.run_feed(gdelt_feed, preloaded_stubs=stubs)

        log.info(
            "GDELT ingestion complete: %d new, %d dup, %d relevant, %d errors (%.1fs)",
            stats.articles_new,
            stats.articles_dup,
            stats.articles_relevant,
            stats.errors,
            stats.duration_seconds or 0,
        )
        return stats
