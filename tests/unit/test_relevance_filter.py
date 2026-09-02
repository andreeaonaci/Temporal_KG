# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

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


class TestSportsExclusion:
    """Regression coverage for the 2026-08-26 finding: a real China-vs-Romania
    table-tennis match report satisfies plain china+romania_co-occurrence but
    is out of scope for the bilateral-relations ontology."""

    def test_sports_competition_excluded(self, filt):
        art = make_article(
            title="China sets up women's final against Japan at table tennis team worlds",
            content=(
                "SPORT/TENNIS\n"
                "China sailed past Romania 3-0 in the women's team semifinals, "
                "reaching the ITTF World Team Table Tennis Championships final."
            ),
        )
        filt.check(art)
        assert art.is_relevant is False
        assert art.relevance_reason == "excluded_sports_content"

    def test_genuine_bilateral_content_not_excluded_by_incidental_sport_word(self, filt):
        # A real diplomatic/economic story should never trip the exclusion
        # just because it lacks the exclusion markers -- confirms the filter
        # doesn't over-exclude ordinary bilateral coverage.
        art = make_article(
            content="China and Romania signed a trade and investment agreement in Bucharest."
        )
        filt.check(art)
        assert art.is_relevant is True
        assert art.relevance_reason == "china+romania_co-occurrence"

    def test_sports_exclusion_can_be_disabled(self):
        old = settings._cfg.get("relevance", {}).get("exclude_sports_content")
        settings._cfg.setdefault("relevance", {})["exclude_sports_content"] = False
        try:
            filt = RelevanceFilter()
            art = make_article(
                content="SPORT/TENNIS\nChina beat Romania in the ITTF semifinal."
            )
            filt.check(art)
            assert art.is_relevant is True
        finally:
            settings._cfg.setdefault("relevance", {})["exclude_sports_content"] = old
