# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for RSS/Atom feed parsing (feedparser.parse() accepts raw XML
strings directly, so these run fully offline -- no network, no mocking)."""

from __future__ import annotations

from src.ingestion.feed_parser import parse_feed

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <item>
      <title>Romania and China sign energy deal</title>
      <link>https://example.com/article-1</link>
      <description>Officials from both countries confirmed the agreement.</description>
      <pubDate>Mon, 01 Jun 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Local weather update</title>
      <link>https://example.com/article-2</link>
      <description>Sunny skies expected this week.</description>
      <pubDate>Tue, 02 Jun 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

MALFORMED_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>Unclosed tag test<link>https://example.com/broken</link></item>
</channel></rss>
"""


def test_parse_feed_extracts_all_entries():
    entries = parse_feed(SAMPLE_RSS)
    assert len(entries) == 2
    assert entries[0]["title"] == "Romania and China sign energy deal"
    assert entries[0]["link"] == "https://example.com/article-1"
    assert "agreement" in entries[0]["summary"]


def test_parse_feed_parses_published_date():
    entries = parse_feed(SAMPLE_RSS)
    published = entries[0]["published"]
    assert published is not None
    assert published.year == 2026
    assert published.month == 6
    assert published.day == 1


def test_parse_feed_skips_entries_without_a_link():
    rss_no_link = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>No link here</title><description>x</description></item>
    </channel></rss>"""
    entries = parse_feed(rss_no_link)
    assert entries == []


def test_parse_feed_handles_malformed_xml_without_crashing():
    # feedparser is deliberately lenient -- real-world RSS feeds are
    # routinely slightly invalid, and this should salvage what it can
    # rather than raising.
    entries = parse_feed(MALFORMED_RSS)
    assert isinstance(entries, list)


def test_parse_feed_returns_empty_list_for_empty_feed():
    empty_rss = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    assert parse_feed(empty_rss) == []
