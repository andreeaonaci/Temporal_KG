"""Integration tests for the GDELT-only ingestion pipeline."""

from __future__ import annotations

import pytest

from src.ingestion.models import ArticleRecord, FeedConfig
from src.ingestion.pipeline import IngestionPipeline
from src.utils.db import DatabaseManager


# ── Full DB schema (mirrors all migrations) ───────────────────────────────────
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

def _make_stub(
    url: str,
    title: str,
    content_clean: str = "",
    source: str = "GDELT China-Romania",
) -> ArticleRecord:
    return ArticleRecord(
        url=url,
        title=title,
        content_clean=content_clean,
        source_name=source,
        feed_url="https://api.gdeltproject.org/api/v2/doc/doc",
        country="bilateral",
    )


@pytest.fixture
def tmp_db(tmp_path):
    db = DatabaseManager(tmp_path / "integration.sqlite")
    db.connect()
    db._conn.executescript(FULL_SCHEMA)
    db.commit()
    yield db
    db.close()


GDELT_FEED = FeedConfig(
    name="GDELT China-Romania",
    url="https://api.gdeltproject.org/api/v2/doc/doc",
    country="bilateral",
    credibility=0.7,
)


class TestPipelineIntegration:

    def test_new_relevant_article_stored(self, tmp_db):
        stubs = [
            _make_stub(
                "https://reuters.com/article/china-romania-1",
                "China and Romania Sign Trade Deal",
                content_clean=(
                    "China and Romania signed a bilateral agreement in Beijing. "
                    "Romanian officials confirmed cooperation plans."
                ),
            )
        ]

        pipeline = IngestionPipeline(db=tmp_db, show_progress=False)
        stats = pipeline.run_feed(GDELT_FEED, preloaded_stubs=stubs)

        assert stats.articles_new == 1
        assert stats.articles_relevant == 1
        assert stats.errors == 0

        row = tmp_db.fetchone(
            "SELECT is_relevant, relevance_reason, content_clean FROM articles LIMIT 1"
        )
        assert row is not None
        assert row["is_relevant"] == 1
        assert "china+romania" in row["relevance_reason"]
        assert "China" in row["content_clean"]

    def test_duplicate_article_not_stored_twice(self, tmp_db):
        pipeline = IngestionPipeline(db=tmp_db, show_progress=False)
        stub1 = _make_stub(
            "https://example.com/article-dup",
            "China Meets Romania Officials",
            content_clean="China met Romanian officials during trade talks.",
        )
        stats1 = pipeline.run_feed(GDELT_FEED, preloaded_stubs=[stub1])

        stub2 = _make_stub(
            "https://example.com/article-dup",
            "China Meets Romania Officials",
            content_clean="China met Romanian officials during trade talks.",
        )
        stats2 = pipeline.run_feed(GDELT_FEED, preloaded_stubs=[stub2])

        assert stats1.articles_new == 1
        assert stats2.articles_new == 0
        assert stats2.articles_dup == 1

        count = tmp_db.fetchone("SELECT COUNT(*) as n FROM articles")
        assert count["n"] == 1

    def test_irrelevant_article_stored_with_flag(self, tmp_db):
        stubs = [
            _make_stub(
                "https://example.com/uk-budget",
                "UK Budget Cuts",
                content_clean=(
                    "The United Kingdom announced budget cuts affecting "
                    "public services across England and Scotland."
                ),
            )
        ]
        pipeline = IngestionPipeline(db=tmp_db, show_progress=False)
        stats = pipeline.run_feed(GDELT_FEED, preloaded_stubs=stubs)

        assert stats.articles_new == 1
        assert stats.articles_relevant == 0

        row = tmp_db.fetchone("SELECT is_relevant FROM articles LIMIT 1")
        assert row["is_relevant"] == 0
