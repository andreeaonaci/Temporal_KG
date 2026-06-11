# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Unit tests for src.ingestion.deduplicator."""

import pytest
from src.ingestion.deduplicator import Deduplicator, sha256
from src.ingestion.models import ArticleRecord
from src.utils.db import DatabaseManager


@pytest.fixture
def tmp_db(tmp_path):
    db = DatabaseManager(tmp_path / "test.sqlite")
    db.connect()
    db.execute(
        """CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            content_hash TEXT,
            content_hash_url TEXT
        )"""
    )
    db.commit()
    yield db
    db.close()


def make_article(url="http://example.com/a", content="some content"):
    art = ArticleRecord(url=url, content_clean=content)
    art.url_hash = sha256(url)
    art.content_hash = sha256(content)
    return art


class TestDeduplicator:

    def test_empty_db_no_duplicates(self, tmp_db):
        dedup = Deduplicator(tmp_db)
        art = make_article()
        is_dup, reason = dedup.is_duplicate(art)
        assert is_dup is False

    def test_url_duplicate_detected(self, tmp_db):
        dedup = Deduplicator(tmp_db)
        art = make_article(url="http://example.com/article-1")
        tmp_db.execute(
            "INSERT INTO articles (url, content_hash) VALUES (?, ?)",
            (art.url, art.content_hash),
        )
        tmp_db.commit()
        dedup.load()
        is_dup, reason = dedup.is_duplicate(art)
        assert is_dup is True
        assert reason == "url_hash"

    def test_content_duplicate_detected(self, tmp_db):
        dedup = Deduplicator(tmp_db)
        art1 = make_article(url="http://a.com/1", content="identical body text")
        art2 = make_article(url="http://b.com/2", content="identical body text")
        tmp_db.execute(
            "INSERT INTO articles (url, content_hash) VALUES (?, ?)",
            (art1.url, art1.content_hash),
        )
        tmp_db.commit()
        dedup.load()
        is_dup, reason = dedup.is_duplicate(art2)
        assert is_dup is True
        assert reason == "content_hash"

    def test_register_prevents_same_run_duplicates(self, tmp_db):
        dedup = Deduplicator(tmp_db)
        art = make_article(url="http://example.com/new")
        # Not in DB yet
        assert dedup.is_duplicate(art)[0] is False
        dedup.register(art)
        # Now it should be seen
        assert dedup.is_duplicate(art)[0] is True

    def test_compute_hashes(self, tmp_db):
        dedup = Deduplicator(tmp_db)
        art = ArticleRecord(url="http://example.com/x", content_clean="hello world")
        dedup.compute_hashes(art)
        assert art.url_hash == sha256("http://example.com/x")
        assert art.content_hash == sha256("hello world")

    def test_load_counts(self, tmp_db):
        tmp_db.execute(
            "INSERT INTO articles (url, content_hash) VALUES (?, ?)",
            ("http://x.com/1", sha256("body1")),
        )
        tmp_db.execute(
            "INSERT INTO articles (url, content_hash) VALUES (?, ?)",
            ("http://x.com/2", sha256("body2")),
        )
        tmp_db.commit()
        dedup = Deduplicator(tmp_db)
        dedup.load()
        assert dedup.url_count == 2
        assert dedup.content_count == 2
