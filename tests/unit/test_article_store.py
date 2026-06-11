# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Unit tests for src.ingestion.article_store."""

import pytest
from pathlib import Path
from datetime import datetime, timezone

from src.ingestion.article_store import ArticleStore
from src.ingestion.models import ArticleRecord, ArticleStatus, IngestionRunStats
from src.utils.db import DatabaseManager


SCHEMA = """
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
    db = DatabaseManager(tmp_path / "test.sqlite")
    db.connect()
    db._conn.executescript(SCHEMA)
    db.commit()
    yield db
    db.close()


@pytest.fixture
def store(tmp_db, tmp_path):
    return ArticleStore(tmp_db, save_json=True, processed_dir=tmp_path / "processed")


def make_article(**kwargs):
    defaults = dict(
        url="https://example.com/article-1",
        title="Test Article",
        source_name="Test Feed",
        feed_url="https://example.com/rss",
        country="general",
        content_raw="<p>Raw HTML</p>",
        content_clean="Raw HTML",
        language="en",
        content_hash="abc123",
        url_hash="def456",
        is_relevant=False,
        relevance_reason="no_match",
        status=ArticleStatus.CLEANED,
        fetched_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return ArticleRecord(**defaults)


class TestArticleStore:

    def test_upsert_feed_creates_row(self, store, tmp_db):
        feed_id = store.upsert_feed("Reuters", "https://reuters.com/rss", "general", 1.0)
        assert isinstance(feed_id, int)
        row = tmp_db.fetchone("SELECT * FROM feeds WHERE id = ?", (feed_id,))
        assert row["name"] == "Reuters"
        assert row["credibility"] == 1.0

    def test_upsert_feed_idempotent(self, store):
        id1 = store.upsert_feed("Reuters", "https://reuters.com/rss", "general", 1.0)
        id2 = store.upsert_feed("Reuters", "https://reuters.com/rss", "general", 1.0)
        assert id1 == id2

    def test_start_and_finish_run(self, store, tmp_db):
        feed_id = store.upsert_feed("Test", "https://t.com/rss", "general", 0.5)
        run_id = store.start_run(feed_id, "https://t.com/rss")
        assert run_id is not None

        stats = IngestionRunStats(
            articles_new=5, articles_dup=2, articles_relevant=1, errors=0, status="success"
        )
        store.finish_run(run_id, stats)

        row = tmp_db.fetchone("SELECT * FROM ingestion_runs WHERE id = ?", (run_id,))
        assert row["articles_new"] == 5
        assert row["articles_dup"] == 2
        assert row["status"] == "success"

    def test_save_article_returns_id(self, store, tmp_db):
        art = make_article()
        row_id = store.save_article(art)
        assert isinstance(row_id, int)
        assert art.db_id == row_id

        row = tmp_db.fetchone("SELECT * FROM articles WHERE id = ?", (row_id,))
        assert row["url"] == art.url
        assert row["title"] == art.title
        assert row["is_relevant"] == 0

    def test_save_relevant_article(self, store, tmp_db):
        art = make_article(is_relevant=True, relevance_reason="china+romania_co-occurrence")
        store.save_article(art)
        row = tmp_db.fetchone("SELECT is_relevant, relevance_reason FROM articles WHERE url = ?", (art.url,))
        assert row["is_relevant"] == 1
        assert row["relevance_reason"] == "china+romania_co-occurrence"

    def test_save_article_writes_json(self, store, tmp_path):
        art = make_article()
        store.save_article(art)
        assert art.json_path != ""
        json_file = Path(art.json_path)
        # Path may be relative — resolve against project root or tmp_path
        # Just check that the file exists somewhere
        found = list((tmp_path / "processed").rglob("*.json"))
        assert len(found) == 1

    def test_update_feed_cache(self, store, tmp_db):
        feed_id = store.upsert_feed("X", "https://x.com/rss", "general", 0.5)
        store.update_feed_cache(feed_id, "etag-123", "Sat, 01 Jan 2024 00:00:00 GMT")
        row = tmp_db.fetchone("SELECT last_etag, last_modified FROM feeds WHERE id = ?", (feed_id,))
        assert row["last_etag"] == "etag-123"
