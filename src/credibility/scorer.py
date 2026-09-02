# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

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
    """Rule-based credibility scorer.

    Three tiers: known-reliable independent outlets score 1.0,
    state-affiliated outlets (real, identifiable, professionally-run --
    but not editorially independent of a government) score a separate,
    lower-but-not-default value, and everything else gets the default.
    Collapsing state media into the same "reliable" bucket as independent
    press would blur a distinction that matters specifically for a project
    studying China-Romania bilateral reporting; scoring it at the bare
    default alongside genuinely unknown sources would also be wrong -- these
    are real, identifiable outlets, not anonymous ones.
    """

    def __init__(self) -> None:
        self._default: float = settings("credibility.default_score", 0.5)
        self._reliable: set[str] = set(
            settings("credibility.known_reliable_domains", [])
        )
        self._state_affiliated: set[str] = set(
            settings("credibility.state_affiliated_domains", [])
        )
        self._state_affiliated_score: float = float(
            settings("credibility.state_affiliated_score", 0.65)
        )

    def score_url(self, url: str) -> float:
        """Return a credibility score for *url*."""
        if not url:
            return self._default
        try:
            # NOTE: str.lstrip(chars) strips any leading characters found in
            # *chars*, not the literal prefix -- "www.wano.com".lstrip("www.")
            # would incorrectly eat the leading "w" of "wano" too.
            # removeprefix() strips the exact substring only.
            domain = urlparse(url).netloc.removeprefix("www.")
        except Exception:
            return self._default

        if domain in self._reliable:
            log.debug("Reliable domain: %s → 1.0", domain)
            return 1.0

        if domain in self._state_affiliated:
            log.debug(
                "State-affiliated domain: %s → %.2f", domain, self._state_affiliated_score
            )
            return self._state_affiliated_score

        log.debug("Unknown domain: %s → %.1f (default)", domain, self._default)
        return self._default
