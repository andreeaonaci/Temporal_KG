# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Composite Temporal-Corroboration Veracity Score (TCVS).

The pre-existing ``ClaimVerifier`` (see ``src/credibility/fake_news.py``) labels
a claim by walking a fixed if/elif cascade over three independent signals
(source credibility, cross-source corroboration, temporal consistency). That
cascade cannot express *how much* each signal contributed to a label, and it
cannot be tuned -- the thresholds are hard-coded control flow, not weights.

TCVS replaces the cascade with a single weighted score,

    TCVS = w_credibility * credibility_signal
         + w_corroboration * corroboration_signal
         + w_temporal * temporal_consistency_signal

with a leave-one-out ablation API (:meth:`VeracityScorer.ablation_report`) so
each signal's marginal contribution to the final score/label can be measured
and reported, instead of asserted. A confirmed contradiction or unresolved
temporal inconsistency still hard-overrides the label to "contested" --
internal inconsistency should never be laundered into "corroborated" by a
high blended score from the other two signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from src.utils.config import settings

DEFAULT_WEIGHTS: dict[str, float] = {
    "credibility": 0.3,
    "corroboration": 0.4,
    "temporal_consistency": 0.3,
}

CORROBORATED_THRESHOLD = 0.65
UNVERIFIED_THRESHOLD = 0.4

# A claim can only be labeled "corroborated" if it clears both the score
# threshold above AND this minimum multi-source evidence gate -- otherwise a
# single very-credible source can outscore the threshold on credibility
# alone. See VeracityScorer._label for the failure mode this prevents.
MIN_CORROBORATION_SUPPORT = 2
MIN_CORROBORATION_DIVERSITY = 2

# Saturation points for the corroboration signal: beyond this many
# supporting records / distinct source domains, additional evidence no
# longer increases the signal. Prevents one prolific single-domain source
# from being indistinguishable from genuine cross-source corroboration.
_SUPPORT_SATURATION = 5
_DIVERSITY_SATURATION = 3

# Penalty per detected temporal inconsistency (end-before-start ranges,
# missing anchors) on the [0, 1] temporal-consistency signal.
_TEMPORAL_PENALTY_PER_ISSUE = 0.4


@dataclass
class VeracityFeatures:
    """Inputs to the veracity score for a single claim."""

    credibility_score: float
    support_count: int
    source_diversity: int
    contradiction_flag: bool = False
    temporal_issue_count: int = 0


@dataclass
class VeracityResult:
    score: float
    label: str
    components: dict[str, float] = field(default_factory=dict)
    weights_used: dict[str, float] = field(default_factory=dict)


def _corroboration_signal(support_count: int, source_diversity: int) -> float:
    support_term = min(max(support_count, 0), _SUPPORT_SATURATION) / _SUPPORT_SATURATION
    diversity_term = (
        min(max(source_diversity, 0), _DIVERSITY_SATURATION) / _DIVERSITY_SATURATION
    )
    return round(0.5 * support_term + 0.5 * diversity_term, 4)


def _temporal_consistency_signal(temporal_issue_count: int) -> float:
    return round(max(0.0, 1.0 - _TEMPORAL_PENALTY_PER_ISSUE * temporal_issue_count), 4)


class VeracityScorer:
    """Blend credibility, corroboration, and temporal-consistency signals."""

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        configured = settings("credibility.veracity_weights", {}) or {}
        self._weights: dict[str, float] = {
            **DEFAULT_WEIGHTS,
            **dict(configured),
            **dict(weights or {}),
        }

    def score(
        self,
        features: VeracityFeatures,
        *,
        ablate: frozenset[str] = frozenset(),
    ) -> VeracityResult:
        raw_components = {
            "credibility": max(0.0, min(1.0, features.credibility_score)),
            "corroboration": _corroboration_signal(
                features.support_count, features.source_diversity
            ),
            "temporal_consistency": _temporal_consistency_signal(
                features.temporal_issue_count
            ),
        }
        active_weights = {
            name: (0.0 if name in ablate else weight)
            for name, weight in self._weights.items()
        }
        total_weight = sum(active_weights.values())
        normalized_weights = (
            {name: weight / total_weight for name, weight in active_weights.items()}
            if total_weight > 0
            else {name: 0.0 for name in active_weights}
        )
        score = sum(
            raw_components[name] * normalized_weights.get(name, 0.0)
            for name in raw_components
        )

        label = self._label(features, score)

        return VeracityResult(
            score=round(score, 4),
            label=label,
            components=raw_components,
            weights_used=normalized_weights,
        )

    @staticmethod
    def _label(features: VeracityFeatures, score: float) -> str:
        """Map (features, blended score) to a verification label.

        The blended score alone is not sufficient: naively thresholding it
        lets a single very-credible source outscore the "corroborated"
        threshold on credibility alone (e.g. credibility=1.0, support=1,
        diversity=1 blends to ~0.71 with the default weights), even though
        "corroborated" is supposed to mean cross-source agreement, not
        "one source we trust a lot". So a genuine multi-source gate
        (``support_count >= MIN_CORROBORATION_SUPPORT`` and
        ``source_diversity >= MIN_CORROBORATION_DIVERSITY``) is enforced
        on top of the score threshold -- the continuous score still governs
        ranking and the contested/partially-corroborated/unverified split,
        it just cannot manufacture "corroborated" out of credibility alone.
        """
        if features.contradiction_flag or features.temporal_issue_count > 0:
            return "contested"
        if features.support_count == 0:
            return "unverified"
        if (
            features.support_count >= MIN_CORROBORATION_SUPPORT
            and features.source_diversity >= MIN_CORROBORATION_DIVERSITY
            and score >= CORROBORATED_THRESHOLD
        ):
            return "corroborated"
        return "unverified" if score < UNVERIFIED_THRESHOLD else "partially_corroborated"

    def ablation_report(self, features: VeracityFeatures) -> dict[str, VeracityResult]:
        """Score *features* once fully, then once with each component removed.

        The delta between ``"full"`` and ``"without_<component>"`` is that
        component's marginal contribution to the score -- the quantity
        Table (veracity ablation) in the paper is built from.
        """
        report = {"full": self.score(features)}
        for component in self._weights:
            report[f"without_{component}"] = self.score(
                features, ablate=frozenset({component})
            )
        return report
