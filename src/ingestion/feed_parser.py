# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.feed_parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure RSS/Atom parsing: given a feed URL, return normalized entry dicts.

Deliberately separate from rss_fetcher.py (which turns entries into
ArticleRecord stubs and knows about FeedConfig/credibility/country) --
this module only knows how to read a feed and hand back plain data,
so it's independently testable without any pipeline machinery.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Any

import feedparser

from src.utils.logger import get_logger

log = get_logger(__name__)


def _struct_time_to_datetime(struct_time) -> datetime | None:
    if not struct_time:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_feed(url: str, *, timeout: int = 15) -> list[dict[str, Any]]:
    """Fetch and parse one RSS/Atom feed, returning normalized entries.

    Each entry dict has: title, link, summary, published (datetime|None).
    Malformed feeds (feedparser sets ``bozo``) still return whatever
    entries feedparser managed to salvage -- real-world RSS feeds are
    routinely slightly invalid XML, and refusing to parse loses articles
    for no benefit.
    """
    parsed = feedparser.parse(url, request_headers={"User-Agent": "temporal-kg-bot/0.1"})

    if getattr(parsed, "bozo", 0):
        log.warning(
            "Feed %s parsed with warnings (%s) -- using %d entries found anyway.",
            url,
            getattr(parsed, "bozo_exception", "unknown issue"),
            len(parsed.entries),
        )

    entries: list[dict[str, Any]] = []
    for entry in parsed.entries:
        link = entry.get("link", "").strip()
        if not link:
            continue
        summary = entry.get("summary", "") or entry.get("description", "")
        published = _struct_time_to_datetime(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )
        entries.append(
            {
                "title": (entry.get("title") or "").strip(),
                "link": link,
                "summary": summary.strip() if summary else "",
                "published": published,
            }
        )
    return entries
