# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.gdelt_fetcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetches China–Romania article stubs from the GDELT 2.0 Full-Text Search API
(https://api.gdeltproject.org/api/v2/doc/doc).

Unlike the RSS path, this module queries GDELT directly and returns
lightweight ArticleRecord stubs (url / title / published_at / source metadata).
No article HTML download is performed in this GDELT-only ingestion mode.

GDELT DOC 2.0 API reference
----------------------------
Endpoint:  https://api.gdeltproject.org/api/v2/doc/doc
Key params:
  query          — search terms (space = AND, supports site:, sourcelang:, …)
  mode           — artlist
  maxrecords     — 1–250
  format         — json
  startdatetime  — YYYYMMDDHHMMSS  (optional)
  enddatetime    — YYYYMMDDHHMMSS  (optional)
  timespan       — 1min … 3months  (alternative to start/end)

Response (mode=artlist, format=json):
  { "articles": [
      { "url": "…", "title": "…", "seendate": "20240101T120000Z",
        "domain": "example.com", "language": "English",
        "sourcecountry": "Romania" }, … ] }

Usage
-----
    fetcher = GdeltFetcher()
    stubs = fetcher.fetch()           # last 1 week
    stubs = fetcher.fetch(timespan="24hours")
    stubs = fetcher.fetch(start_date=datetime(2024,1,1), end_date=datetime(2024,2,1))
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import requests

from src.ingestion.models import ArticleRecord
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
_GDELT_DATE_FMT = "%Y%m%dT%H%M%SZ"


def _parse_seendate(raw: str) -> Optional[datetime]:
    """Parse GDELT ``seendate`` field (``YYYYMMDDTHHMMSSZ`` or ``YYYYMMDDTHHMMZ``)."""
    if not raw:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%MZ", "%Y%m%d"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    log.debug("Could not parse GDELT seendate: %r", raw)
    return None


def _gdelt_dt(dt: datetime) -> str:
    """Format a datetime as a GDELT ``startdatetime``/``enddatetime`` param."""
    return dt.strftime("%Y%m%d%H%M%S")


class GdeltFetcher:
    """
    Queries the GDELT 2.0 Full-Text Search API and returns article stubs.

    Parameters
    ----------
    query : str | None
        Override the default query from ``settings.gdelt.query``.
    timeout : int | None
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        query: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._base_url: str = settings("gdelt.base_url", _GDELT_BASE)
        self._query: str = query or settings("gdelt.query", "China Romania")
        self._max_records: int = int(settings("gdelt.max_records", 250))
        self._mode: str = settings("gdelt.mode", "artlist")
        self._format: str = settings("gdelt.format", "json")
        self._default_timespan: str = settings("gdelt.default_timespan", "1week")
        self._default_credibility: float = float(
            settings("gdelt.default_credibility", 0.7)
        )
        self._timeout: int = timeout or int(settings("gdelt.request_timeout", 30))
        self._rate_delay: float = float(settings("gdelt.rate_limit_delay", 1.0))
        self._ua: str = settings("ingestion.user_agent", "temporal-kg-bot/0.1")

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch(
        self,
        *,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        timespan: str | None = None,
        max_records: int | None = None,
    ) -> list[ArticleRecord]:
        """
        Query GDELT for China–Romania articles and return article stubs.

        Supply either *start_date* / *end_date* **or** *timespan* (not both).
        When none are given, the configured ``gdelt.default_timespan`` is used.

        Parameters
        ----------
        start_date : datetime | None
            Inclusive range start (UTC).
        end_date : datetime | None
            Inclusive range end (UTC).
        timespan : str | None
            GDELT timespan token, e.g. ``"24hours"``, ``"1week"``.
        max_records : int | None
            Override the configured max_records cap (1–250).

        Returns
        -------
        list[ArticleRecord]
            Stubs with url / title / published_at / source metadata filled in.
        """
        params = self._build_params(
            start_date=start_date,
            end_date=end_date,
            timespan=timespan,
            max_records=max_records,
        )

        log.info(
            "GDELT query: %r  |  timespan=%s  |  maxrecords=%s",
            params.get("query"),
            params.get("timespan", f"{params.get('startdatetime')}→{params.get('enddatetime')}"),
            params.get("maxrecords"),
        )

        raw_items = self._request(params)
        if raw_items is None:
            return []

        stubs = [self._to_stub(item) for item in raw_items if item.get("url")]
        log.info("GDELT returned %d article stubs", len(stubs))
        return stubs

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_params(
        self,
        *,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        timespan: str | None,
        max_records: int | None,
    ) -> dict:
        cap = min(int(max_records or self._max_records), 250)
        params: dict = {
            "query": self._query,
            "mode": self._mode,
            "format": self._format,
            "maxrecords": str(cap),
        }

        if start_date or end_date:
            if start_date:
                params["startdatetime"] = _gdelt_dt(start_date)
            if end_date:
                params["enddatetime"] = _gdelt_dt(end_date)
        else:
            params["timespan"] = timespan or self._default_timespan

        return params

    def _request(self, params: dict) -> Optional[list[dict]]:
        """Issue the GDELT HTTP request; return the raw ``articles`` list or None."""
        time.sleep(self._rate_delay)
        try:
            resp = requests.get(
                self._base_url,
                params=params,
                timeout=(10, self._timeout),
                headers={"User-Agent": self._ua},
                allow_redirects=True,
            )
            if resp.status_code != 200:
                log.warning(
                    "GDELT API returned HTTP %s for query %r",
                    resp.status_code,
                    params.get("query"),
                )
                return None

            data = resp.json()
            articles = data.get("articles")
            if articles is None:
                log.info("GDELT response contained no 'articles' key (empty result set).")
                return []
            return articles

        except Exception as exc:
            log.error("GDELT API request failed: %s", exc)
            return None

    def _to_stub(self, item: dict) -> ArticleRecord:
        """Convert a raw GDELT article dict to an ArticleRecord stub."""
        domain = item.get("domain", "")
        source_country = item.get("sourcecountry", "unknown")
        language_raw = item.get("language", "")
        snippet = ""

        # Prefer human-readable summary fields when present in API payloads.
        for key in ("snippet", "description", "excerpt"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                snippet = value.strip()
                break

        return ArticleRecord(
            url=item["url"].strip(),
            title=(item.get("title") or "").strip(),
            source_name=f"GDELT:{domain}" if domain else "GDELT",
            feed_url=self._base_url,
            country=source_country,
            published_at=_parse_seendate(item.get("seendate", "")),
            language=_gdelt_language_code(language_raw),
            content_clean=snippet,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

_GDELT_LANG_MAP: dict[str, str] = {
    "english": "en",
    "romanian": "ro",
    "chinese": "zh",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "russian": "ru",
    "arabic": "ar",
    "portuguese": "pt",
    "italian": "it",
}


def _gdelt_language_code(gdelt_lang: str) -> str:
    """Convert a GDELT language name (e.g. ``'English'``) to an ISO 639-1 code."""
    return _GDELT_LANG_MAP.get(gdelt_lang.strip().lower(), "")
