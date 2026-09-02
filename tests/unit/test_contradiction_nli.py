# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for NLI-based semantic contradiction detection.

The corroboration-integration behaviour is tested with a fake
``ContradictionDetector`` double (deterministic, no model needed) so the
"structural flag can't see this, semantic flag can" case is verified
without transformers/torch in the test environment. A separate real-model
integration test is skipped (not failed) when transformers/torch or the
model weights aren't available -- same pattern as
``test_hybrid_extraction.py``'s spaCy skip and
``test_semantic_corroboration.py``'s embedding-model skip.
"""

from __future__ import annotations

import json

import pytest

from src.credibility.contradiction_nli import ContradictionDetector
from src.credibility.corroboration import CorroborationAnalyzer
from src.credibility.semantic_similarity import SemanticSimilarityScorer


class FakeContradictionDetector(ContradictionDetector):
    """Deterministic stand-in: any pair mentioning both 'high' and 'low' contradicts."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def available(self) -> bool:
        return True

    def contradiction_score(self, sentence_a: str, sentence_b: str) -> float:
        markers = {"high", "low"}
        found = {m for m in markers if m in sentence_a.lower() or m in sentence_b.lower()}
        return 1.0 if found == markers else 0.0

    def entailment_score(self, premise: str, hypothesis: str) -> float:
        return 0.0


class AlwaysRelevantSemanticScorer(SemanticSimilarityScorer):
    """Stand-in that reports every pair as topically relevant (similarity 1.0).

    Semantic *merging* is out of scope for these tests -- every fixture
    article below shares participants/date/event_type, so exact-signature
    grouping already puts them in one group before merging would ever run.
    This double exists only to satisfy the relevance pre-filter in
    ``_detect_semantic_contradiction`` so the NLI-contradiction behaviour
    under test isn't accidentally masked by an unrelated stand-in returning
    low similarity.
    """

    def __init__(self) -> None:
        self.threshold = 0.75

    def available(self) -> bool:
        return True

    def embed_many(self, texts):
        return [[1.0] for _ in texts]


def test_contradiction_score_symmetric_marker_pair():
    detector = FakeContradictionDetector()
    assert detector.is_contradiction("The turnout was high.", "The turnout was low.") is True
    assert detector.is_contradiction("The turnout was high.", "The turnout was strong.") is False


def _write_events_article(
    events_dir, entities_dir, temporals_dir, *, article_id, url, sentence, event_type
):
    (entities_dir / f"{article_id}.entities.json").write_text(
        json.dumps({"article_id": article_id, "entities": [], "mentions": []}),
        encoding="utf-8",
    )
    (temporals_dir / f"{article_id}.temporals.json").write_text(
        json.dumps({"article_id": article_id, "temporal_expressions": []}),
        encoding="utf-8",
    )
    (events_dir / f"{article_id}.events.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "source_article": {
                    "url": url,
                    "title": "t",
                    "published_at": "2025-05-04",
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
                        # group -> structural flag can never fire here, since
                        # event_type/date are identical by construction.
                        "participant_entity_ids": ["shared-entity"],
                        "temporal_id": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_semantic_contradiction_flag_fires_when_structural_flag_cannot(tmp_path):
    entities_dir, temporals_dir, events_dir = (
        tmp_path / "e",
        tmp_path / "t",
        tmp_path / "v",
    )
    for d in (entities_dir, temporals_dir, events_dir):
        d.mkdir()

    # Identical participants/date/event_type -> exact-signature group of 2,
    # so the structural contradiction_flag (which only looks at event_types
    # and time_windows within the group) is always False here.
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-1",
        url="https://www.reuters.com/a",
        sentence="Turnout at the summit was reported as high.",
        event_type="DiplomaticMeeting",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="Turnout at the summit was reported as low.",
        event_type="DiplomaticMeeting",
    )

    analyzer = CorroborationAnalyzer(
        semantic_scorer=AlwaysRelevantSemanticScorer(),
        contradiction_detector=FakeContradictionDetector(),
    )
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    row = results["events"][0]
    assert row["structural_contradiction_flag"] is False
    assert row["semantic_contradiction_flag"] is True
    assert row["contradiction_flag"] is True


def test_no_semantic_contradiction_when_sentences_agree(tmp_path):
    entities_dir, temporals_dir, events_dir = (
        tmp_path / "e",
        tmp_path / "t",
        tmp_path / "v",
    )
    for d in (entities_dir, temporals_dir, events_dir):
        d.mkdir()

    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-1",
        url="https://www.reuters.com/a",
        sentence="Turnout at the summit was reported as high.",
        event_type="DiplomaticMeeting",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="Turnout at the summit was reported as strong.",
        event_type="DiplomaticMeeting",
    )

    analyzer = CorroborationAnalyzer(
        semantic_scorer=AlwaysRelevantSemanticScorer(),
        contradiction_detector=FakeContradictionDetector(),
    )
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    row = results["events"][0]
    assert row["structural_contradiction_flag"] is False
    assert row["semantic_contradiction_flag"] is False
    assert row["contradiction_flag"] is False


def test_disabled_nli_contradiction_never_flags(tmp_path):
    entities_dir, temporals_dir, events_dir = (
        tmp_path / "e",
        tmp_path / "t",
        tmp_path / "v",
    )
    for d in (entities_dir, temporals_dir, events_dir):
        d.mkdir()

    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-1",
        url="https://www.reuters.com/a",
        sentence="Turnout at the summit was reported as high.",
        event_type="DiplomaticMeeting",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="Turnout at the summit was reported as low.",
        event_type="DiplomaticMeeting",
    )

    analyzer = CorroborationAnalyzer(
        semantic_scorer=AlwaysRelevantSemanticScorer(),
        contradiction_detector=FakeContradictionDetector(),
    )
    analyzer._use_nli_contradiction = False
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    row = results["events"][0]
    assert row["semantic_contradiction_flag"] is False
    assert row["contradiction_flag"] is False


def _real_detector_or_skip() -> ContradictionDetector:
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    detector = ContradictionDetector()
    if not detector.available():
        pytest.skip("contradiction NLI model weights unavailable (no network on first run?)")
    return detector


def test_real_model_scores_conflicting_facts_higher_than_paraphrase():
    detector = _real_detector_or_skip()
    contradiction_score = detector.contradiction_score(
        "Twelve people were injured in the incident.",
        "Only two people were injured in the incident.",
    )
    paraphrase_score = detector.contradiction_score(
        "Romania and China signed the energy deal on Friday.",
        "The energy deal between Romania and China was signed Friday.",
    )
    assert contradiction_score > paraphrase_score
