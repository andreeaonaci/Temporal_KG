# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.google_news_resolver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resolves Google News RSS wrapper URLs to the real publisher URL.

Google News RSS ``<link>`` entries point at ``news.google.com/rss/articles/...``
redirect pages, not the originating publisher. Confirmed by hand (2026-08-19):
following the HTTP redirect just lands on another Google-owned interstitial
page (still ``news.google.com``, HTTP 200 with an empty body over HEAD, a
consent-wall page over GET) -- the real destination is only resolved
client-side via JavaScript in Google's single-page app, never present as a
plain link in the static HTML. That means every URL-keyed signal downstream
collapses to "news.google.com" for every Google-News-sourced article unless
resolved first:

- ``CorroborationAnalyzer._source_domain()`` -- source_diversity undercounts,
  since six articles from six different real outlets, all wrapped, look like
  one source.
- ``CredibilityScorer.score_url()`` -- can never match known_reliable_domains,
  since it's checking "news.google.com" instead of the real publisher.

Uses the ``googlenewsdecoder`` PyPI package, which reverse-engineers Google's
internal batchexecute endpoint to recover the real URL. This is NOT a
documented, stable API -- it can break if Google changes the mechanism, so
every call here is wrapped to fail soft: on any error, the original wrapper
URL is returned unchanged rather than failing the article (or the whole
ingestion run). Verified working against a live URL during development
(resolved to romania-insider.com), not just assumed to work from the
package's own claims.

Each resolution is a real network round-trip (plus the package's own
built-in rate-limit interval), so this adds real wall-clock time to any RSS
feed with many Google News entries -- accepted here since ingestion runs are
already treated as long-running batch jobs (see run_big_experiment.sh), not
something expected to finish instantly.
"""

from __future__ import annotations

from urllib.parse import urlparse

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_GOOGLE_NEWS_HOST = "news.google.com"


def is_google_news_wrapper(url: str) -> bool:
    try:
        return urlparse(url).netloc == _GOOGLE_NEWS_HOST
    except ValueError:
        return False


def resolve(url: str) -> str:
    """Return the real publisher URL for a Google News wrapper link.

    Returns *url* unchanged if it isn't a Google News wrapper link, if
    resolution is disabled via settings, if the decoder package isn't
    installed, or if decoding fails for any reason -- callers never need to
    handle a resolution failure specially, the wrapper URL is always a safe
    fallback (it still works as a dedup key, just not as a diversity/
    credibility signal).
    """
    if not is_google_news_wrapper(url):
        return url
    if not bool(settings("ingestion.resolve_google_news_urls", True)):
        return url

    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError:
        log.warning(
            "googlenewsdecoder not installed -- Google News URLs will stay as "
            "wrapper links (source_domain will read as news.google.com for "
            "every such article, undermining corroboration diversity and "
            "credibility scoring). Install with: pip install googlenewsdecoder"
        )
        return url

    try:
        result = gnewsdecoder(url, interval=1)
    except Exception as exc:
        log.warning("Google News URL decode failed for %s: %s", url, exc)
        return url

    if result.get("status") and result.get("decoded_url"):
        return result["decoded_url"]

    log.warning("Could not decode Google News URL %s: %s", url, result)
    return url
