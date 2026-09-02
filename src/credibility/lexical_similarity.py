# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.credibility.lexical_similarity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Jaccard token-overlap similarity -- the standard bag-of-words baseline in
fact-checking/corroboration literature (see Lendvai & Reichel 2016's
lexical-overlap features for rumorous-claim contradiction detection).

``SemanticSimilarityScorer`` (embeddings) and ``ContradictionDetector``
(NLI) are compared against *each other* in every ablation so far -- this
class exists to give both a real prior-art-style baseline to beat, not just
an "on vs. off" self-comparison. Duck-type compatible with
``SemanticSimilarityScorer``'s public interface (``available``,
``embed``/``embed_many``, ``cosine_similarity``, ``is_match``, and a
``.threshold`` attribute) so it can be swapped into
``CorroborationAnalyzer`` or any evaluation script without other code
changes -- see ``evaluate_corroboration.py --baseline lexical``.
"""

from __future__ import annotations

import re

from src.utils.config import settings

DEFAULT_THRESHOLD = 0.3
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9À-ɏ]+")


class LexicalOverlapScorer:
    """Jaccard similarity over lowercased word tokens. No model, no loading."""

    def __init__(self) -> None:
        self.threshold = float(
            settings("credibility.lexical_baseline.threshold", DEFAULT_THRESHOLD)
        )

    def available(self) -> bool:
        return True

    @staticmethod
    def _tokens(text: str) -> frozenset[str]:
        return frozenset(_TOKEN_PATTERN.findall((text or "").lower()))

    def embed(self, text: str) -> frozenset[str]:
        return self._tokens(text)

    def embed_many(self, texts: list[str]) -> list[frozenset[str]]:
        return [self._tokens(t) for t in texts]

    @staticmethod
    def cosine_similarity(a: frozenset[str] | None, b: frozenset[str] | None) -> float:
        """Named to match SemanticSimilarityScorer's interface; this is
        actually Jaccard similarity (intersection over union), not cosine --
        there's no vector here, just token sets."""
        if not a or not b:
            return 0.0
        union = a | b
        if not union:
            return 0.0
        return len(a & b) / len(union)

    def is_match(self, a: frozenset[str] | None, b: frozenset[str] | None) -> bool:
        return self.cosine_similarity(a, b) >= self.threshold
