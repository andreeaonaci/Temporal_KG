# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Integration tests for the RSS ingestion pipeline -- the RSS-side twin of
test_pipeline_integration.py. Uses a fake RssFetcher (no network) so these
run offline; feed_parser.py's own offline XML-parsing behaviour is covered
separately in tests/unit/test_feed_parser.py."""

from __future__ import annotations

import pytest

from src.ingestion.models import ArticleRecord, FeedConfig
from src.ingestion.rss_pipeline import RssIngestionPipeline
from src.utils.db import DatabaseManager

# Reuses the same schema as test_pipeline_integration.py's FULL_SCHEMA.
FULL_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    content_raw TEXT,
    content_clean TEXT,
    language TEXT,
    country TEXT,
    published_at TEXT,
    fetched_at TEXT,
    status TEXT DEFAULT 'raw',
    content_hash TEXT,
    content_hash_url TEXT,
    is_relevant INTEGER DEFAULT 0,
    relevance_reason TEXT,
    raw_html_path TEXT,
    json_path TEXT,
    language_detected TEXT,
    fetch_error TEXT,
    credibility REAL
);
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    country TEXT,
    credibility REAL DEFAULT 0.5,
    last_fetched_at TEXT,
    last_etag TEXT,
    last_modified TEXT,
    articles_total INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER,
    feed_url TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT,
    articles_new INTEGER DEFAULT 0,
    articles_dup INTEGER DEFAULT 0,
    articles_relevant INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'
);
"""


@pytest.fixture
def tmp_db(tmp_path):
    db = DatabaseManager(tmp_path / "rss_integration.sqlite")
    db.connect()
    db._conn.executescript(FULL_SCHEMA)
    db.commit()
    yield db
    db.close()


class FakeRssFetcher:
    """Returns preloaded stubs per feed url instead of hitting the network."""

    def __init__(self, stubs_by_url: dict[str, list[ArticleRecord]]) -> None:
        self._stubs_by_url = stubs_by_url

    def fetch_feed(self, feed_cfg: FeedConfig) -> list[ArticleRecord]:
        return self._stubs_by_url.get(feed_cfg.url, [])


FEED_A = FeedConfig(name="Feed A", url="https://a.example.com/rss", country="Romania", credibility=0.8)
FEED_B = FeedConfig(name="Feed B", url="https://b.example.com/rss", country="general", credibility=0.6)


def _stub(url, title, content_clean, source):
    return ArticleRecord(url=url, title=title, content_clean=content_clean, source_name=source, country="Romania")


def test_rss_pipeline_ingests_relevant_article_from_a_configured_feed(tmp_db):
    fetcher = FakeRssFetcher(
        {
            FEED_A.url: [
                _stub(
                    "https://a.example.com/article-1",
                    "China and Romania Sign Trade Deal",
                    "China and Romania signed a bilateral agreement in Beijing.",
                    "Feed A",
                )
            ]
        }
    )
    pipeline = RssIngestionPipeline(show_progress=False, fetcher=fetcher, db=tmp_db)
    all_stats = pipeline.run(feeds=[FEED_A])

    assert len(all_stats) == 1
    assert all_stats[0].feed_name == "Feed A"
    assert all_stats[0].articles_new == 1
    assert all_stats[0].articles_relevant == 1


def test_rss_pipeline_runs_every_configured_feed_independently(tmp_db):
    fetcher = FakeRssFetcher(
        {
            FEED_A.url: [_stub("https://a.example.com/1", "t", "China Romania cooperation.", "Feed A")],
            FEED_B.url: [_stub("https://b.example.com/1", "t", "Unrelated local news.", "Feed B")],
        }
    )
    pipeline = RssIngestionPipeline(show_progress=False, fetcher=fetcher, db=tmp_db)
    all_stats = pipeline.run(feeds=[FEED_A, FEED_B])

    assert [s.feed_name for s in all_stats] == ["Feed A", "Feed B"]
    assert all(s.articles_new == 1 for s in all_stats)


def test_rss_pipeline_handles_empty_feed_gracefully(tmp_db):
    fetcher = FakeRssFetcher({})  # no stubs for any feed
    pipeline = RssIngestionPipeline(show_progress=False, fetcher=fetcher, db=tmp_db)
    all_stats = pipeline.run(feeds=[FEED_A])

    assert all_stats[0].articles_new == 0
    assert all_stats[0].status == "success"


def test_rss_pipeline_records_a_failed_fetch_without_stopping_other_feeds(tmp_db):
    class ExplodingFetcher:
        def fetch_feed(self, feed_cfg):
            if feed_cfg.url == FEED_A.url:
                raise ConnectionError("simulated network failure")
            return [_stub("https://b.example.com/1", "t", "China Romania news.", "Feed B")]

    pipeline = RssIngestionPipeline(show_progress=False, fetcher=ExplodingFetcher(), db=tmp_db)
    all_stats = pipeline.run(feeds=[FEED_A, FEED_B])

    assert all_stats[0].feed_name == "Feed A"
    assert all_stats[0].status == "failed"
    assert all_stats[1].feed_name == "Feed B"
    assert all_stats[1].status == "success"
    assert all_stats[1].articles_new == 1


def test_run_with_no_configured_feeds_returns_empty_list(tmp_db):
    pipeline = RssIngestionPipeline(show_progress=False, fetcher=FakeRssFetcher({}), db=tmp_db)
    assert pipeline.run(feeds=[]) == []
