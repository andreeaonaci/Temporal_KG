# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for temporal-aware contradiction resolution.

An NLI-contradictory pair should only become ``semantic_contradiction_flag``
when the two events' extracted dates are temporally coincident (per Allen's
Interval Algebra in src/temporal/reasoner.py); if the dates are sequential
(before/after/meets/met_by), it's reclassified as ``claim_evolution_flag``
instead -- a lifecycle transition ("proposed" -> "signed"), not a genuine
disagreement about the same fact. Uses the same fake-detector pattern as
test_contradiction_nli.py so this runs without transformers/torch.
"""

from __future__ import annotations

import json

from src.credibility.contradiction_nli import ContradictionDetector
from src.credibility.corroboration import CorroborationAnalyzer
from src.credibility.semantic_similarity import SemanticSimilarityScorer


class FakeContradictionDetector(ContradictionDetector):
    """Deterministic stand-in: any pair mentioning both 'proposed' and 'signed'
    (or 'high'/'low') is flagged as an NLI contradiction, regardless of dates --
    isolates the temporal-gate behaviour from real NLI accuracy."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def available(self) -> bool:
        return True

    def contradiction_score(self, sentence_a: str, sentence_b: str) -> float:
        marker_sets = [{"proposed", "signed"}, {"high", "low"}, {"ratified", "signed"}]
        lowered = f"{sentence_a.lower()} {sentence_b.lower()}"
        for markers in marker_sets:
            if all(m in lowered for m in markers):
                return 1.0
        return 0.0

    # Lifecycle state keywords for TradeAgreement -- a claim sentence
    # containing one of these words "entails" the matching state's
    # NLI hypothesis template (which also contains that word), and nothing
    # else, isolating lifecycle-verification behaviour from real NLI
    # accuracy the same way contradiction_score does above.
    _STATE_KEYWORDS = ("proposed", "negotiating", "signed", "ratified", "rejected")

    def entailment_score(self, premise: str, hypothesis: str) -> float:
        lowered_premise = premise.lower()
        lowered_hypothesis = hypothesis.lower()
        for keyword in self._STATE_KEYWORDS:
            if keyword in lowered_premise and keyword in lowered_hypothesis:
                return 1.0
        return 0.0


class AlwaysRelevantSemanticScorer(SemanticSimilarityScorer):
    """Stand-in that reports every pair as topically relevant."""

    def __init__(self) -> None:
        self.threshold = 0.75

    def available(self) -> bool:
        return True

    def embed_many(self, texts):
        return [[1.0] for _ in texts]


def _write_article_with_date(
    events_dir, entities_dir, temporals_dir, *, article_id, url, sentence, date, event_type
):
    (entities_dir / f"{article_id}.entities.json").write_text(
        json.dumps({"article_id": article_id, "entities": [], "mentions": []}),
        encoding="utf-8",
    )
    (temporals_dir / f"{article_id}.temporals.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "temporal_expressions": [
                    {
                        "temporal_id": f"time-{article_id}",
                        "text": date,
                        "kind": "absolute_date",
                        "normalized": date,
                        "granularity": "day",
                        "resolved": True,
                        "ambiguous": False,
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (events_dir / f"{article_id}.events.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "source_article": {
                    "url": url,
                    "title": "t",
                    "published_at": date,
                },
                "events": [
                    {
                        "event_id": f"event-{article_id}",
                        "event_type": event_type,
                        "trigger": "x",
                        "normalized_trigger": "x",
                        "sentence": sentence,
                        "confidence": 0.9,
                        "sentence_index": 0,
                        # Same participants -> same exact signature -> same
                        # group regardless of date, so grouping never depends
                        # on the dates under test here.
                        "participant_entity_ids": ["shared-entity"],
                        "temporal_id": f"time-{article_id}",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _run(
    tmp_path,
    *,
    sentence_a,
    date_a,
    sentence_b,
    date_b,
    use_temporal_gate=True,
    use_lifecycle_verification=True,
    event_type="InvestmentProject",
):
    entities_dir, temporals_dir, events_dir = (
        tmp_path / "e",
        tmp_path / "t",
        tmp_path / "v",
    )
    for d in (entities_dir, temporals_dir, events_dir):
        d.mkdir()

    _write_article_with_date(
        events_dir, entities_dir, temporals_dir,
        article_id="art-1", url="https://www.reuters.com/a",
        sentence=sentence_a, date=date_a, event_type=event_type,
    )
    _write_article_with_date(
        events_dir, entities_dir, temporals_dir,
        article_id="art-2", url="https://www.bbc.com/b",
        sentence=sentence_b, date=date_b, event_type=event_type,
    )

    analyzer = CorroborationAnalyzer(
        semantic_scorer=AlwaysRelevantSemanticScorer(),
        contradiction_detector=FakeContradictionDetector(),
    )
    analyzer._use_temporal_gate = use_temporal_gate
    analyzer._use_lifecycle_verification = use_lifecycle_verification
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )
    return results["events"][0]


def test_sequential_dates_reclassify_nli_contradiction_as_evolution(tmp_path):
    row = _run(
        tmp_path,
        sentence_a="The energy deal was proposed by both sides.",
        date_a="2025-01-10",
        sentence_b="The energy deal was signed by both governments.",
        date_b="2025-03-01",
    )
    assert row["semantic_contradiction_flag"] is False
    assert row["claim_evolution_flag"] is True
    assert row["contradiction_flag"] is False


def test_coincident_dates_keep_nli_contradiction_as_a_real_contradiction(tmp_path):
    row = _run(
        tmp_path,
        sentence_a="Turnout at the summit was reported as high.",
        date_a="2025-06-01",
        sentence_b="Turnout at the summit was reported as low.",
        date_b="2025-06-01",
    )
    assert row["semantic_contradiction_flag"] is True
    assert row["claim_evolution_flag"] is False
    assert row["contradiction_flag"] is True


def test_missing_dates_fall_back_to_raw_nli_as_contradiction(tmp_path):
    row = _run(
        tmp_path,
        sentence_a="The energy deal was proposed by both sides.",
        date_a="not-a-date",
        sentence_b="The energy deal was signed by both governments.",
        date_b="not-a-date",
    )
    assert row["semantic_contradiction_flag"] is True
    assert row["claim_evolution_flag"] is False
    assert row["contradiction_flag"] is True


def test_disabling_temporal_gate_flags_sequential_claims_as_contradiction(tmp_path):
    row = _run(
        tmp_path,
        sentence_a="The energy deal was proposed by both sides.",
        date_a="2025-01-10",
        sentence_b="The energy deal was signed by both governments.",
        date_b="2025-03-01",
        use_temporal_gate=False,
    )
    # This is exactly the false positive the gate exists to fix: without it,
    # a legitimate lifecycle transition reads as a contradiction.
    assert row["semantic_contradiction_flag"] is True
    assert row["claim_evolution_flag"] is False


def test_legal_lifecycle_transition_stays_classified_as_evolution(tmp_path):
    # proposed -> signed is a legal TradeAgreement transition.
    row = _run(
        tmp_path,
        sentence_a="The trade agreement was proposed by both sides.",
        date_a="2025-01-10",
        sentence_b="The trade agreement was signed by both governments.",
        date_b="2025-03-01",
        event_type="TradeAgreement",
    )
    assert row["claim_evolution_flag"] is True
    assert row["lifecycle_violation_flag"] is False
    assert row["contradiction_flag"] is False


def test_illegal_lifecycle_transition_is_downgraded_from_evolution_to_contradiction(tmp_path):
    # "ratified" is a terminal TradeAgreement state -- nothing can legally
    # follow it, so a later report of "signed" is an impossible sequence,
    # not a lifecycle transition. The pairwise temporal gate alone can't
    # see this (it only knows the dates are sequential); lifecycle
    # verification is what catches it.
    row = _run(
        tmp_path,
        sentence_a="The trade agreement was ratified by parliament.",
        date_a="2025-01-10",
        sentence_b="The trade agreement was signed by both governments.",
        date_b="2025-03-01",
        event_type="TradeAgreement",
    )
    assert row["claim_evolution_flag"] is False
    assert row["lifecycle_violation_flag"] is True
    assert row["semantic_contradiction_flag"] is True
    assert row["contradiction_flag"] is True


def test_disabling_lifecycle_verification_trusts_evolution_unconditionally(tmp_path):
    row = _run(
        tmp_path,
        sentence_a="The trade agreement was ratified by parliament.",
        date_a="2025-01-10",
        sentence_b="The trade agreement was signed by both governments.",
        date_b="2025-03-01",
        event_type="TradeAgreement",
        use_lifecycle_verification=False,
    )
    # This is exactly the gap lifecycle verification exists to close:
    # without it, an impossible sequence still reads as legitimate evolution.
    assert row["claim_evolution_flag"] is True
    assert row["lifecycle_violation_flag"] is False
    assert row["contradiction_flag"] is False
