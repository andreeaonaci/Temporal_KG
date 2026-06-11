# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Temporal extraction for cleaned news articles."""

from __future__ import annotations

import re
from typing import Any

from src.extraction.pipeline_utils import (
    get_article_id,
    parse_article_datetime,
    stable_id,
)
from src.temporal.date_normaliser import DateNormaliser
from src.temporal.heideltime_client import HeidelTimeClient
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

TEMPORAL_PATTERNS = [
    re.compile(r"\b\d{1,2}\s+[A-Za-zăâîșțĂÂÎȘȚ]+\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-zăâîșțĂÂÎȘȚ]+\s+\d{1,2},\s*\d{4}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:yesterday|today|tomorrow|last week|next week|last month|until\s+\d{4}|by\s+\d{4}|ieri|astăzi|azi|mâine|maine|săptămâna trecută|saptamana trecuta|săptămâna viitoare|saptamana viitoare|luna trecută|luna trecuta|până\s+în\s+\d{4}|pana\s+in\s+\d{4})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:from|between|din|între)\s+[^.!,;]+?\s+(?:to|and|până\s+în|pana\s+in|și|si)\s+[^.!,;]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:for|within|timp\s+de)\s+\d+\s+(?:days?|weeks?|months?|years?|zile|săptămâni|saptamani|luni|ani)\b",
        re.IGNORECASE,
    ),
]
SENTENCE_PATTERN = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)


class RegexTemporalExtractor:
    """Detect and normalize temporal expressions using regex rules."""

    def __init__(self) -> None:
        self._normaliser = DateNormaliser()

    def extract_article(self, article: dict[str, Any]) -> dict[str, Any]:
        article_id = get_article_id(article)
        anchor = parse_article_datetime(article)
        content = article.get("content_clean") or ""
        temporals: list[dict[str, Any]] = []
        seen: set[tuple[int, int, str]] = set()

        for sentence_index, match in enumerate(SENTENCE_PATTERN.finditer(content)):
            sentence = match.group(0).strip()
            if not sentence:
                continue
            sentence_start = match.start()
            for pattern in TEMPORAL_PATTERNS:
                for item in pattern.finditer(sentence):
                    start_char = sentence_start + item.start()
                    end_char = sentence_start + item.end()
                    key = (start_char, end_char, item.group(0).lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    text = item.group(0).strip()
                    normalized = self._normaliser.normalise(text, anchor)
                    temporals.append(
                        {
                            "temporal_id": stable_id(
                                article_id, text, start_char, end_char
                            ),
                            "article_id": article_id,
                            "text": text,
                            "kind": normalized["kind"],
                            "normalized": normalized["value"],
                            "granularity": normalized["granularity"],
                            "resolved": normalized["resolved"],
                            "ambiguous": normalized["ambiguous"],
                            "reason": normalized["reason"],
                            "sentence": sentence,
                            "sentence_index": sentence_index,
                            "start_char": start_char,
                            "end_char": end_char,
                            "confidence": round(normalized["confidence"], 3),
                            "anchor_date": normalized["anchor_date"],
                        }
                    )

        return {
            "article_id": article_id,
            "source_article": {
                "article_id": article_id,
                "url": article.get("url"),
                "title": article.get("title"),
                "published_at": article.get("published_at"),
            },
            "temporal_expressions": temporals,
        }


class HeidelTimeTemporalExtractor:
    """Use HeidelTime to extract TIMEX3 expressions from article text."""

    def __init__(self) -> None:
        self._client = HeidelTimeClient()

    def extract_article(self, article: dict[str, Any]) -> dict[str, Any]:
        article_id = get_article_id(article)
        content = article.get("content_clean") or ""
        anchor = parse_article_datetime(article)

        if not content.strip():
            return {
                "article_id": article_id,
                "source_article": {
                    "article_id": article_id,
                    "url": article.get("url"),
                    "title": article.get("title"),
                    "published_at": article.get("published_at"),
                },
                "temporal_expressions": [],
            }

        temporals = self._client.extract_timex3(
            content,
            article_id=article_id,
            anchor=anchor,
        )
        return {
            "article_id": article_id,
            "source_article": {
                "article_id": article_id,
                "url": article.get("url"),
                "title": article.get("title"),
                "published_at": article.get("published_at"),
            },
            "temporal_expressions": temporals,
        }


class TemporalExtractor:
    """Facade that selects the temporal engine based on settings."""

    def __init__(self) -> None:
        engine = str(settings("temporal.engine", "regex")).strip().lower()
        use_heideltime = settings("temporal.heideltime.enabled", False)
        if engine == "heideltime" and use_heideltime:
            log.info("Temporal engine: HeidelTime")
            self._impl: Any = HeidelTimeTemporalExtractor()
        else:
            log.info("Temporal engine: regex")
            self._impl = RegexTemporalExtractor()

    def extract_article(self, article: dict[str, Any]) -> dict[str, Any]:
        return self._impl.extract_article(article)
