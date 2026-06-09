"""
temporal_kg.src.credibility.scorer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Assigns a credibility score [0.0 – 1.0] to articles based on their
source domain.  Scores are configurable via settings.yaml.

Usage
-----
    from src.credibility.scorer import CredibilityScorer

    scorer = CredibilityScorer()
    score = scorer.score_url("https://www.reuters.com/article/...")
    # 1.0
"""

from __future__ import annotations

from urllib.parse import urlparse

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class CredibilityScorer:
    """Rule-based credibility scorer."""

    def __init__(self) -> None:
        self._default: float = settings("credibility.default_score", 0.5)
        self._reliable: set[str] = set(
            settings("credibility.known_reliable_domains", [])
        )

    def score_url(self, url: str) -> float:
        """Return a credibility score for *url*."""
        if not url:
            return self._default
        try:
            domain = urlparse(url).netloc.lstrip("www.")
        except Exception:
            return self._default

        if domain in self._reliable:
            log.debug("Reliable domain: %s → 1.0", domain)
            return 1.0

        log.debug("Unknown domain: %s → %.1f (default)", domain, self._default)
        return self._default
