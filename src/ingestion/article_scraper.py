# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.article_scraper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetches and extracts the real body text of an article page.

Confirmed 2026-08-24: GDELT-sourced articles never had their body text
fetched -- pipeline.py built ``content_clean`` from title + GDELT snippet
only, and GDELT's DOC 2.0 API essentially never returns a snippet, so every
GDELT article's "content" was just its headline. 303/303 articles in the
corpus at the time had ``content_raw == ""``. Downstream extraction (event
sentences, claims, corroboration) was therefore running on headline text,
not article content -- this module closes that gap by actually downloading
the article page and extracting its main text with trafilatura (boilerplate
removal: nav bars, related-links, comments, ads stripped out).

Best-effort by design: news sites are unreliable (paywalls, dead links,
anti-bot pages, transient errors). On any failure this returns an empty
string rather than raising, so callers can fall back to title/snippet text
instead of failing the whole article.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
import trafilatura

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ScrapedArticle:
    text: str
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error


class ArticleScraper:
    """Downloads an article URL and extracts its main body text.

    Parameters
    ----------
    timeout : int | None
        HTTP request timeout in seconds (default: ``ingestion.request_timeout``).
    """

    def __init__(self, timeout: int | None = None) -> None:
        self._timeout: int = timeout or int(settings("ingestion.request_timeout", 10))
        self._ua: str = settings("ingestion.user_agent", "temporal-kg-bot/0.1")
        self._retry_attempts: int = int(settings("ingestion.retry_attempts", 3))
        self._retry_backoff: float = float(settings("ingestion.retry_backoff", 2.0))

    def fetch(self, url: str) -> ScrapedArticle:
        """Download *url* and return its extracted main text.

        Retries transient failures up to ``retry_attempts`` times with
        exponential backoff; the final failure's error message is returned
        rather than raised.
        """
        last_error = ""
        for attempt in range(self._retry_attempts):
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": self._ua},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                extracted = trafilatura.extract(
                    resp.text,
                    favor_recall=True,
                    include_comments=False,
                    include_tables=False,
                )
                if not extracted or not extracted.strip():
                    return ScrapedArticle(text="", error="no_extractable_text")
                return ScrapedArticle(text=extracted.strip())
            except Exception as exc:  # noqa: BLE001 -- best-effort scraping, log and fall back
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self._retry_attempts - 1:
                    time.sleep(self._retry_backoff * (attempt + 1))
        log.debug("Article scrape failed for %s: %s", url[:80], last_error)
        return ScrapedArticle(text="", error=last_error)
