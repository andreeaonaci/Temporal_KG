# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.ingestion.relevance_filter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Determines whether an article is relevant to the China–Romania project.

Relevance rule
--------------
The matcher supports configurable modes:

- strict: must contain at least one China term AND one Romania term.
- feed_aware: strict OR one-side term match if feed country is the other side
    (e.g. China term in a Romania feed article).
- either: contain at least one China OR Romania term.

Both term lists are configurable via settings.yaml under
``relevance.china_terms`` and ``relevance.romania_terms``.
"""

from __future__ import annotations

import re
from src.ingestion.models import ArticleRecord
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

# Fallback defaults (overridden by settings.yaml)
_DEFAULT_CHINA_TERMS = [
    "China", "Chinese", "Beijing", "PRC", "Sino", "Xi Jinping",
    "CCP", "People's Republic",
]
_DEFAULT_ROMANIA_TERMS = [
    "Romania", "Romanian", "Bucharest",
]
_DEFAULT_MODE = "strict"

# Confirmed as a real false-positive source (2026-08-26): a genuine China vs.
# Romania table-tennis match (both national teams literally competing)
# satisfies plain china+romania_co-occurrence, but sports results are out of
# scope for this project's bilateral-*relations* ontology (none of the 11
# event types -- DiplomaticMeeting, TradeAgreement, etc. -- fit "sports
# competition"), and full-text scraping means the whole match report (not
# just a headline) now flows into event extraction, where a sentence from an
# unrelated match on the same multi-game roundup page can get picked up.
# These markers are deliberately narrow -- competition-governing-body
# acronyms and explicit sports-section tags -- rather than generic sports
# vocabulary, so a genuine diplomatic/economic story is extremely unlikely to
# trip this exclusion by coincidence.
_DEFAULT_SPORTS_EXCLUSION_MARKERS = [
    "ITTF", "FIFA", "UEFA", "FIBA", "IOC ", "NBA", "ATP", "WTA",
    "SPORT/", "SPORT /", "SPORTS NEWS",
]


def _build_pattern(terms: list[str]) -> re.Pattern:
    """
    Compile a case-insensitive whole-word regex from a list of terms.
    Multi-word terms (e.g. "Xi Jinping") are matched as-is (no word boundary
    after a space).
    """
    escaped = [re.escape(t) for t in terms]
    # Use word-boundaries where possible; for multi-word terms the boundary
    # is only enforced around the whole phrase.
    pattern = r"(?i)(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)"
    return re.compile(pattern)


class RelevanceFilter:
    """
    Checks whether an article mentions both China and Romania.

    Usage
    -----
        filt = RelevanceFilter()
        article = filt.check(article)
        if article.is_relevant:
            ...
    """

    def __init__(self) -> None:
        china_terms: list[str] = settings("relevance.china_terms", _DEFAULT_CHINA_TERMS)
        romania_terms: list[str] = settings("relevance.romania_terms", _DEFAULT_ROMANIA_TERMS)
        mode = str(settings("relevance.mode", _DEFAULT_MODE)).strip().lower()
        if mode not in {"strict", "feed_aware", "either"}:
            log.warning("Unknown relevance.mode='%s'; falling back to 'strict'", mode)
            mode = "strict"

        self._china_pattern = _build_pattern(china_terms)
        self._romania_pattern = _build_pattern(romania_terms)
        self._mode = mode

        self._exclude_sports = bool(settings("relevance.exclude_sports_content", True))
        sports_markers: list[str] = settings(
            "relevance.sports_exclusion_markers", _DEFAULT_SPORTS_EXCLUSION_MARKERS
        )
        self._sports_pattern = (
            re.compile(
                "|".join(re.escape(m) for m in sports_markers), re.IGNORECASE
            )
            if sports_markers
            else None
        )

        log.debug(
            "RelevanceFilter: mode=%s, %d China terms, %d Romania terms",
            self._mode,
            len(china_terms),
            len(romania_terms),
        )

    def check(self, article: ArticleRecord) -> ArticleRecord:
        """
        Evaluate relevance and set article.is_relevant / article.relevance_reason.
        The article is modified in place and also returned.
        """
        corpus = f"{article.title}\n{article.content_clean}"

        has_china = bool(self._china_pattern.search(corpus))
        has_romania = bool(self._romania_pattern.search(corpus))
        country = (article.country or "").strip().lower()

        if self._mode == "strict":
            article.is_relevant = has_china and has_romania
        elif self._mode == "feed_aware":
            article.is_relevant = (
                (has_china and has_romania)
                or (has_china and country == "romania")
                or (has_romania and country == "china")
            )
        else:  # either
            article.is_relevant = has_china or has_romania

        if (
            article.is_relevant
            and self._exclude_sports
            and self._sports_pattern is not None
            and self._sports_pattern.search(corpus)
        ):
            article.is_relevant = False
            article.relevance_reason = "excluded_sports_content"
            return article

        if article.is_relevant:
            if has_china and has_romania:
                article.relevance_reason = "china+romania_co-occurrence"
            elif has_china:
                article.relevance_reason = "china_only_feed_aware"
            else:
                article.relevance_reason = "romania_only_feed_aware"
        elif has_china:
            article.relevance_reason = "china_only"
        elif has_romania:
            article.relevance_reason = "romania_only"
        else:
            article.relevance_reason = "no_match"

        return article

    def extract_matches(self, text: str, max_terms: int = 6) -> tuple[list[str], list[str]]:
        """
        Return matched China and Romania terms as they appear in *text*.

        Results are case-insensitive unique matches in first-seen order,
        capped by *max_terms* per side.
        """
        if not text:
            return [], []

        def _uniq(matches: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for m in matches:
                k = m.casefold()
                if k in seen:
                    continue
                seen.add(k)
                out.append(m)
                if len(out) >= max_terms:
                    break
            return out

        china = _uniq([m.group(0) for m in self._china_pattern.finditer(text)])
        romania = _uniq([m.group(0) for m in self._romania_pattern.finditer(text)])
        return china, romania

    def is_relevant(self, text: str) -> bool:
        """Convenience: check a raw string."""
        return bool(self._china_pattern.search(text)) and bool(
            self._romania_pattern.search(text)
        )
