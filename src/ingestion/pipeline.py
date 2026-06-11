# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestrates the full ingestion pipeline for GDELT-sourced articles:

  1. Receive article stubs from the GDELT fetcher
  2. Deduplicate by URL hash  →  skip known articles
    3. Build text corpus from GDELT fields (title/snippet)
    4. Detect language
    5. Optionally translate to English
    6. Compute content hash  →  second dedup pass
    7. Check relevance  →  China + Romania co-occurrence
    8. Persist to SQLite + JSON files

Usage
-----
    from src.ingestion.pipeline import IngestionPipeline

    pipeline = IngestionPipeline()
    stats = pipeline.run_feed(feed_cfg, preloaded_stubs=stubs)
    print(stats.articles_new, "new articles")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from tqdm import tqdm

from src.ingestion.article_store import ArticleStore
from src.ingestion.deduplicator import Deduplicator
from src.ingestion.language_detector import detect_language
from src.ingestion.models import ArticleRecord, ArticleStatus, FeedConfig, IngestionRunStats
from src.ingestion.relevance_filter import RelevanceFilter
from src.utils.db import DatabaseManager, get_db
from src.utils.logger import get_logger
from src.ingestion.translator import Translator


log = get_logger(__name__)


class IngestionPipeline:
    """
    Full ingestion pipeline for GDELT-sourced articles.

    Parameters
    ----------
    db : DatabaseManager | None
        Pass an open DB to reuse; otherwise a new one is created per
        ``run_feed`` call (auto-closed on exit).
    show_progress : bool
        Display a tqdm progress bar per feed.
    """

    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        show_progress: bool = True,
    ) -> None:
        self._external_db = db is not None
        self._db: Optional[DatabaseManager] = db
        self._show_progress = show_progress

        # Shared stateless components
        self._relevance = RelevanceFilter()
        self._translator = Translator()

    # ── Public API ────────────────────────────────────────────────────────────

    def run_feed(
        self,
        feed_cfg: FeedConfig,
        preloaded_stubs: list[ArticleRecord],
    ) -> IngestionRunStats:
        """
        Run the pipeline for a batch of GDELT article stubs.

        Parameters
        ----------
        feed_cfg : FeedConfig
            Feed configuration (name, URL, country, credibility).
        preloaded_stubs : list[ArticleRecord]
            Article stubs fetched from the GDELT API.

        Returns an IngestionRunStats summary.
        """
        stats = IngestionRunStats(
            feed_name=feed_cfg.name,
            feed_url=feed_cfg.url,
            started_at=datetime.now(timezone.utc),
        )

        owns_db = self._db is None
        if owns_db:
            self._db = get_db().connect()
        db = self._db
        store = ArticleStore(db)
        dedup = Deduplicator(db)
        dedup.load()

        feed_id = store.upsert_feed(
            feed_cfg.name, feed_cfg.url, feed_cfg.country, feed_cfg.credibility
        )
        run_id = store.start_run(feed_id, feed_cfg.url)

        try:
            stubs = preloaded_stubs
            log.info(
                "Feed '%s': processing %d GDELT stubs",
                feed_cfg.name,
                len(stubs),
            )

            stats.articles_seen = len(stubs)

            if not stubs:
                log.info("No new entries for feed: %s", feed_cfg.name)
                stats.status = "success"
                stats.finished_at = datetime.now(timezone.utc)
                store.finish_run(run_id, stats)
                return stats

            # ── Steps 2–8: GDELT-only processing and persistence ─────────────
            iterator = tqdm(
                stubs,
                desc=feed_cfg.name[:40],
                unit="art",
                disable=not self._show_progress,
            )
            for stub in iterator:
                result = self._process_article(stub, dedup, store)
                if result == "new":
                    stats.articles_new += 1
                    if stub.is_relevant:
                        stats.articles_relevant += 1
                elif result == "dup":
                    stats.articles_dup += 1
                else:
                    stats.errors += 1

            store.increment_feed_article_count(feed_id, stats.articles_new)
            stats.status = "success"

        except Exception as exc:
            log.error("Pipeline error for feed '%s': %s", feed_cfg.name, exc, exc_info=True)
            stats.status = "failed"
            stats.errors += 1

        finally:
            stats.finished_at = datetime.now(timezone.utc)
            store.finish_run(run_id, stats)
            if owns_db:
                db.close()
                self._db = None
        log.info(
            "Feed '%s' done: %d new, %d dup, %d relevant, %d errors (%.1fs)",
            feed_cfg.name,
            stats.articles_new,
            stats.articles_dup,
            stats.articles_relevant,
            stats.errors,
            stats.duration_seconds or 0,
        )
        return stats

    # ── Internal ──────────────────────────────────────────────────────────────

    def _process_article(
        self,
        article: ArticleRecord,
        dedup: Deduplicator,
        store: ArticleStore,
    ) -> str:
        """
        Process a single article stub through the full pipeline.

        Returns "new" | "dup" | "error"
        """
        # ── URL dedup (fast path, no download needed) ─────────────────────────
        article.url_hash = __import__("hashlib").sha256(
            article.url.encode()
        ).hexdigest()
        url_dup, _ = dedup.is_duplicate(article)
        if url_dup:
            log.debug("SKIP (url_dup): %s", article.url[:80])
            return "dup"

        # ── GDELT-only text preparation (no URL fetch/scraping) ─────────────
        article.fetched_at = datetime.now(timezone.utc)
        gdelt_text_parts = [article.title.strip(), article.content_clean.strip()]
        article.content_clean = "\n".join(part for part in gdelt_text_parts if part).strip()
        article.content_raw = ""

        if not article.content_clean and article.url:
            article.content_clean = article.url

        article.status = ArticleStatus.CLEANED

        # ── Language detection ─────────────────────────────────────────────────
        article.language = detect_language(article.content_clean)


        # ── Translate to English ──────────────────────────────────────────────
        try:
            self._translator.translate(article)
        except Exception as exc:
            article.status = ArticleStatus.ERROR
            article.fetch_error = f"translation_failed: {exc}"
            dedup.compute_hashes(article)
            dedup.register(article)
            store.save_article(article)
            log.warning("SKIP (translation_error): %s", article.url[:80])
            return "error"

        # ── Content hash + second dedup pass ──────────────────────────────────
        dedup.compute_hashes(article)
        content_dup, reason = dedup.is_duplicate(article)
        if content_dup:
            log.debug("SKIP (content_dup=%s): %s", reason, article.url[:80])
            return "dup"

        # ── Relevance ─────────────────────────────────────────────────────────
        self._relevance.check(article)

        # ── Persist ───────────────────────────────────────────────────────────
        row_id = store.save_article(article)
        if row_id is None:
            return "error"

        dedup.register(article)
        return "new"
