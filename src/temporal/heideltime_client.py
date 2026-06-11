# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""HeidelTime integration for TIMEX3 extraction using py-heideltime Python package."""

from __future__ import annotations

import re
import os
import stat
from datetime import datetime
from typing import Any
from pathlib import Path

from src.extraction.pipeline_utils import stable_id
from src.temporal.date_normaliser import DateNormaliser
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_SENTENCE_PATTERN = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)


class HeidelTimeClient:
    """Run HeidelTime using py-heideltime Python package and parse TIMEX3 tags."""

    def __init__(self) -> None:
        self._language = settings("temporal.heideltime.language", "en")
        self._document_type = settings("temporal.heideltime.document_type", "news")
        self._normaliser = DateNormaliser()
        self._heideltime_available = False

        try:
            from py_heideltime import py_heideltime as py_heideltime_func
            self._heideltime_func = py_heideltime_func
            self._heideltime_available = True
            self._ensure_tree_tagger_executable()
            log.info("py-heideltime successfully loaded")
        except ImportError:
            log.warning(
                "py-heideltime not installed. Install with: pip install py-heideltime. "
                "Note: Requires Java JDK and Perl installed on system."
            )
            self._heideltime_func = None

    def extract_timex3(
        self,
        text: str,
        *,
        article_id: str,
        anchor: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Extract temporal expressions using py-heideltime.

        Args:
            text: The text to extract temporal expressions from
            article_id: Unique identifier for the article
            anchor: Document creation time for resolving relative dates

        Returns:
            List of temporal expression dictionaries
        """
        if not text.strip():
            return []

        if not self._heideltime_available or self._heideltime_func is None:
            log.warning(
                "py-heideltime not available, falling back to regex extraction"
            )
            return self._fallback_regex(text, article_id, anchor)

        try:
            # Map internal language codes to py-heideltime expected format
            language_map = {
                "en": "English",
                "english": "English",
                "de": "German",
                "german": "German",
                "es": "Spanish",
                "spanish": "Spanish",
                "pt": "Portuguese",
                "portuguese": "Portuguese",
                "fr": "French",
                "french": "French",
                "it": "Italian",
                "italian": "Italian",
                "nl": "Dutch",
                "dutch": "Dutch",
            }

            language = language_map.get(
                self._language.lower(),
                "English"
            )

            # Prepare document creation time
            document_creation_time = anchor.strftime("%Y-%m-%d") if anchor else None

            # Call py-heideltime
            timexs = self._heideltime_func(
                text,
                language=language,
                document_type=self._document_type,
                document_creation_time=document_creation_time or "yyyy-mm-dd"
            )

            # Convert py-heideltime output to project format
            return self._parse_py_heideltime_output(
                timexs,
                text,
                article_id=article_id,
                anchor=anchor,
            )

        except Exception as exc:
            log.error("py-heideltime extraction failed: %s", exc, exc_info=True)
            log.info("Falling back to regex extraction")
            return self._fallback_regex(text, article_id, anchor)

    def _parse_py_heideltime_output(
        self,
        timexs: list[dict],
        article_text: str,
        *,
        article_id: str,
        anchor: datetime | None,
    ) -> list[dict[str, Any]]:
        """Convert py-heideltime output format to project format.

        py-heideltime returns:
        [
            {
                "text": "August 31st",
                "tid": "t2",
                "type": "DATE",
                "value": "1939-08-31",
                "span": [6, 17]
            }
        ]
        """
        records = self._coerce_timex_records(timexs, article_text)

        temporals: list[dict[str, Any]] = []
        sentences = list(_SENTENCE_PATTERN.finditer(article_text))

        for timex in records:
            text = str(timex.get("text", "")).strip()
            if not text:
                continue

            value = timex.get("value")
            timex_type = str(timex.get("type", "")).lower()
            span = timex.get("span")
            if isinstance(span, (list, tuple)) and len(span) >= 2:
                start_char = int(span[0])
                end_char = int(span[1])
            else:
                start_char, end_char = self._locate_text_span(text, article_text)

            # Normalize the temporal value
            normalized = self._normalize_timex(text, value, anchor)

            # Find sentence containing this temporal expression
            sentence_index, sentence_text = self._locate_sentence(
                start_char, sentences
            )

            temporals.append(
                {
                    "temporal_id": stable_id(article_id, text, start_char, end_char),
                    "article_id": article_id,
                    "text": text,
                    "kind": normalized["kind"] or timex_type or "timex3",
                    "normalized": normalized["value"],
                    "granularity": normalized["granularity"],
                    "resolved": normalized["resolved"],
                    "ambiguous": normalized["ambiguous"],
                    "reason": normalized.get("reason"),
                    "sentence": sentence_text,
                    "sentence_index": sentence_index,
                    "start_char": start_char,
                    "end_char": end_char,
                    "confidence": round(normalized["confidence"], 3),
                    "anchor_date": normalized["anchor_date"],
                    "source": "py-heideltime",
                }
            )

        return temporals

    @staticmethod
    def _coerce_timex_records(
        timexs: list[Any],
        article_text: str,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        def add_pair(value: Any, text: Any) -> None:
            if text is None:
                return
            text_str = str(text).strip()
            if not text_str:
                return
            records.append({"value": value, "text": text_str, "type": "DATE"})

        for item in timexs:
            if isinstance(item, dict):
                records.append(item)
                continue

            if isinstance(item, tuple) and len(item) >= 2:
                first, second = item[0], item[1]
                # py-heideltime commonly returns (value, text)
                add_pair(first, second)
                continue

            if isinstance(item, list):
                if item and all(isinstance(pair, tuple) and len(pair) >= 2 for pair in item):
                    for pair in item:
                        add_pair(pair[0], pair[1])
                    continue
                if item and all(isinstance(value, str) for value in item):
                    # Fallback for nested [timexes, annotated_text, original_text, stats]
                    # We do not want the metadata strings here.
                    continue

            if isinstance(item, str):
                # Ignore annotated/original text blobs returned by py-heideltime.
                continue

        return records

    @staticmethod
    def _locate_text_span(text: str, article_text: str) -> tuple[int, int]:
        pos = article_text.find(text)
        if pos == -1:
            return 0, 0
        return pos, pos + len(text)

    @staticmethod
    def _ensure_tree_tagger_executable() -> None:
        try:
            import py_heideltime
        except ImportError:
            return

        package_dir = Path(py_heideltime.__file__).resolve().parent
        binary_path = package_dir / "Heideltime" / "TreeTaggerLinux" / "bin" / "tree-tagger"
        if not binary_path.exists():
            return

        mode = binary_path.stat().st_mode
        if mode & stat.S_IXUSR:
            return

        try:
            binary_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            log.info("Enabled executable bit for TreeTagger binary at %s", binary_path)
        except OSError as exc:
            log.warning("Could not mark TreeTagger executable at %s: %s", binary_path, exc)

    def _normalize_timex(
        self,
        text: str,
        value: str | None,
        anchor: datetime | None,
    ) -> dict[str, Any]:
        """Normalize TIMEX3 value to project format."""
        if value:
            value = value.strip()
            # Duration format (ISO 8601 period)
            if value.startswith("P"):
                return {
                    "kind": "duration",
                    "value": value,
                    "granularity": None,
                    "confidence": 0.88,
                    "resolved": True,
                    "ambiguous": False,
                    "anchor_date": (anchor.date().isoformat() if anchor else ""),
                    "reason": None,
                }
            # Interval format
            if "/" in value:
                start, end = value.split("/", 1)
                return {
                    "kind": "interval",
                    "value": {"start": start, "end": end},
                    "granularity": None,
                    "confidence": 0.9,
                    "resolved": True,
                    "ambiguous": False,
                    "anchor_date": (anchor.date().isoformat() if anchor else ""),
                    "reason": None,
                }
            # Absolute date
            return {
                "kind": "absolute_date",
                "value": value,
                "granularity": self._infer_granularity(value),
                "confidence": 0.92,
                "resolved": True,
                "ambiguous": False,
                "anchor_date": (anchor.date().isoformat() if anchor else ""),
                "reason": None,
            }

        # If no value provided, use our normalizer
        return self._normaliser.normalise(text, anchor)

    @staticmethod
    def _infer_granularity(value: str) -> str | None:
        """Infer temporal granularity from ISO 8601 date string."""
        if len(value) >= 10:
            return "day"
        if len(value) == 7:
            return "month"
        if len(value) == 4:
            return "year"
        return None

    @staticmethod
    def _locate_sentence(
        char_pos: int,
        sentences: list[re.Match[str]],
    ) -> tuple[int, str]:
        """Find which sentence contains the character position."""
        for idx, match in enumerate(sentences):
            if match.start() <= char_pos < match.end():
                return idx, match.group(0).strip()
        # Fallback to first sentence
        return 0, (sentences[0].group(0).strip() if sentences else "")

    def _fallback_regex(
        self,
        text: str,
        article_id: str,
        anchor: datetime | None,
    ) -> list[dict[str, Any]]:
        """Fallback to regex-based extraction when py-heideltime unavailable."""
        from src.temporal.temporal_extractor import RegexTemporalExtractor

        extractor = RegexTemporalExtractor()
        return extractor.extract_article(
            {
                "article_id": article_id,
                "content_clean": text,
                "published_at": anchor.isoformat() if anchor else None,
            }
        ).get("temporal_expressions", [])
