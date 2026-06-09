"""Unit tests for src.ingestion.relevance_filter."""

import pytest
from src.ingestion.models import ArticleRecord
from src.ingestion.relevance_filter import RelevanceFilter
from src.utils.config import settings


@pytest.fixture
def filt():
    return RelevanceFilter()


def make_article(title="", content=""):
    return ArticleRecord(url="http://example.com/test", title=title, content_clean=content)


class TestRelevanceFilter:

    def test_both_terms_relevant(self, filt):
        art = make_article(content="China and Romania signed a trade deal in Beijing.")
        filt.check(art)
        assert art.is_relevant is True
        assert art.relevance_reason == "china+romania_co-occurrence"

    def test_china_only_not_relevant(self, filt):
        art = make_article(content="China announced new economic policies.")
        filt.check(art)
        assert art.is_relevant is False
        assert art.relevance_reason == "china_only"

    def test_romania_only_not_relevant(self, filt):
        art = make_article(content="Romania joined the EU summit in Bucharest.")
        filt.check(art)
        assert art.is_relevant is False
        assert art.relevance_reason == "romania_only"

    def test_no_match(self, filt):
        art = make_article(content="The US and UK discussed trade relations.")
        filt.check(art)
        assert art.is_relevant is False
        assert art.relevance_reason == "no_match"

    def test_match_in_title(self, filt):
        art = make_article(
            title="China's Ambassador visits Bucharest",
            content="The visit was brief.",
        )
        filt.check(art)
        assert art.is_relevant is True

    def test_alias_chinese(self, filt):
        art = make_article(content="A Chinese company invested in Romanian infrastructure.")
        filt.check(art)
        assert art.is_relevant is True

    def test_case_insensitive(self, filt):
        art = make_article(content="CHINA is negotiating with ROMANIA.")
        filt.check(art)
        assert art.is_relevant is True

    def test_word_boundary(self, filt):
        # "RomaniaXYZ" should NOT match
        art = make_article(content="China has no relation with RomaniaXYZ.")
        filt.check(art)
        assert art.is_relevant is False

    def test_is_relevant_convenience(self, filt):
        assert filt.is_relevant("Beijing signs pact with Bucharest") is True
        assert filt.is_relevant("Only China here") is False


def test_feed_aware_country_bridge_from_romania_feed():
    old_mode = settings._cfg.get("relevance", {}).get("mode")
    settings._cfg.setdefault("relevance", {})["mode"] = "feed_aware"
    try:
        filt = RelevanceFilter()
        art = ArticleRecord(
            url="http://example.com/test-feed-aware-1",
            country="Romania",
            content_clean="China announced new economic policies.",
        )
        filt.check(art)
        assert art.is_relevant is True
        assert art.relevance_reason == "china_only_feed_aware"
    finally:
        settings._cfg.setdefault("relevance", {})["mode"] = old_mode


def test_feed_aware_country_bridge_from_china_feed():
    old_mode = settings._cfg.get("relevance", {}).get("mode")
    settings._cfg.setdefault("relevance", {})["mode"] = "feed_aware"
    try:
        filt = RelevanceFilter()
        art = ArticleRecord(
            url="http://example.com/test-feed-aware-2",
            country="China",
            content_clean="Romania approved a transport project.",
        )
        filt.check(art)
        assert art.is_relevant is True
        assert art.relevance_reason == "romania_only_feed_aware"
    finally:
        settings._cfg.setdefault("relevance", {})["mode"] = old_mode
