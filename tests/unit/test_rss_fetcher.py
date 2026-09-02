# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

from datetime import datetime, timezone

from src.ingestion.models import FeedConfig
from src.ingestion.rss_fetcher import RssFetcher, load_configured_feeds

SAMPLE_FEED = FeedConfig(
    name="Test Feed", url="https://example.com/feed.xml", country="Romania", credibility=0.7
)


def test_to_stub_maps_entry_fields_onto_article_record():
    entry = {
        "title": "Romania and China sign energy deal",
        "link": "https://example.com/article-1",
        "summary": "Officials confirmed the agreement.",
        "published": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }
    stub = RssFetcher._to_stub(entry, SAMPLE_FEED, resolved_link=entry["link"])

    assert stub.url == "https://example.com/article-1"
    assert stub.title == "Romania and China sign energy deal"
    assert stub.content_clean == "Officials confirmed the agreement."
    assert stub.source_name == "Test Feed"
    assert stub.feed_url == "https://example.com/feed.xml"
    assert stub.country == "Romania"
    assert stub.published_at == entry["published"]


def test_to_stub_uses_resolved_link_not_the_original_wrapper_url():
    entry = {
        "title": "t",
        "link": "https://news.google.com/rss/articles/CBMi...",
        "summary": "s",
        "published": None,
    }
    stub = RssFetcher._to_stub(entry, SAMPLE_FEED, resolved_link="https://real-publisher.example.com/article")
    assert stub.url == "https://real-publisher.example.com/article"


def test_fetch_feed_resolves_google_news_wrapper_urls(monkeypatch):
    monkeypatch.setattr(
        "src.ingestion.rss_fetcher.parse_feed",
        lambda url: [
            {
                "title": "Wrapped article",
                "link": "https://news.google.com/rss/articles/CBMi123",
                "summary": "s",
                "published": None,
            },
            {
                "title": "Direct article",
                "link": "https://real-outlet.example.com/article-2",
                "summary": "s",
                "published": None,
            },
        ],
    )
    monkeypatch.setattr(
        "src.ingestion.rss_fetcher.google_news_resolver.resolve",
        lambda url: "https://resolved.example.com/real-article"
        if "news.google.com" in url
        else url,
    )
    stubs = RssFetcher().fetch_feed(SAMPLE_FEED)

    assert stubs[0].url == "https://resolved.example.com/real-article"
    assert stubs[1].url == "https://real-outlet.example.com/article-2"


def test_load_configured_feeds_builds_feed_configs_from_settings(monkeypatch):
    fake_feeds = [
        {"name": "Feed A", "url": "https://a.example.com/rss", "country": "Romania", "credibility": 0.8},
        {"name": "Feed B", "url": "https://b.example.com/rss"},  # defaults for country/credibility
    ]
    monkeypatch.setattr(
        "src.ingestion.rss_fetcher.settings",
        lambda key, default=None: fake_feeds if key == "ingestion.rss_feeds" else default,
    )
    feeds = load_configured_feeds()

    assert len(feeds) == 2
    assert feeds[0] == FeedConfig(name="Feed A", url="https://a.example.com/rss", country="Romania", credibility=0.8)
    assert feeds[1].name == "Feed B"
    assert feeds[1].country == "general"  # default
    assert feeds[1].credibility == 0.5  # default


def test_load_configured_feeds_returns_empty_list_when_unset(monkeypatch):
    monkeypatch.setattr("src.ingestion.rss_fetcher.settings", lambda key, default=None: default)
    assert load_configured_feeds() == []
