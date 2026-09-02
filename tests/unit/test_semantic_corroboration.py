# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for semantic (embedding-similarity) corroboration matching.

The pure math (cosine similarity, threshold comparison) is tested directly,
with no model required. The corroboration-merge logic is tested with a fake
``SemanticSimilarityScorer`` double that returns deterministic embeddings,
so the union-find/bucketing behaviour is verified without needing
transformers/torch or a model download in the test environment. A separate,
real-model integration test is skipped (not failed) when transformers/torch
or the model weights aren't available -- same pattern as
``test_hybrid_extraction.py``'s spaCy skip.
"""

from __future__ import annotations

import json

import pytest

from src.credibility.corroboration import CorroborationAnalyzer
from src.credibility.semantic_similarity import SemanticSimilarityScorer


class FakeSemanticScorer(SemanticSimilarityScorer):
    """Deterministic stand-in: sentences sharing a marker word embed identically."""

    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold
        self._markers = ("alpha", "beta", "gamma")

    def available(self) -> bool:
        return True

    def embed_many(self, texts):
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [1.0 if marker in lowered else 0.0 for marker in self._markers]
            )
        return vectors


def test_cosine_similarity_identical_vectors_is_one():
    assert SemanticSimilarityScorer.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert SemanticSimilarityScorer.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_handles_missing_embedding():
    assert SemanticSimilarityScorer.cosine_similarity(None, [1.0, 0.0]) == 0.0


def test_is_match_respects_threshold():
    scorer = SemanticSimilarityScorer()
    scorer.threshold = 0.8
    assert scorer.is_match([1.0, 0.0], [1.0, 0.0]) is True
    assert scorer.is_match([1.0, 0.0], [0.0, 1.0]) is False


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
                        "participant_entity_ids": [article_id],  # forces distinct exact signatures
                        "temporal_id": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_semantic_merge_folds_paraphrased_claims_into_one_group(tmp_path):
    entities_dir, temporals_dir, events_dir = (
        tmp_path / "e",
        tmp_path / "t",
        tmp_path / "v",
    )
    for d in (entities_dir, temporals_dir, events_dir):
        d.mkdir()

    # Different participants -> different exact signatures, but both
    # sentences carry the "alpha" marker -> the fake scorer embeds them
    # identically, so semantic merge should fold them into one group.
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-1",
        url="https://www.reuters.com/a",
        sentence="Romania and China signed the alpha energy deal.",
        event_type="InvestmentProject",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="Bucharest and Beijing finalized the alpha energy agreement.",
        event_type="InvestmentProject",
    )

    analyzer = CorroborationAnalyzer(semantic_scorer=FakeSemanticScorer())
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    event_groups = results["events"]
    assert len(event_groups) == 1
    assert event_groups[0]["support_count"] == 2
    assert event_groups[0]["source_diversity"] == 2
    assert event_groups[0]["semantically_merged_keys"]


def test_semantic_merge_does_not_fold_dissimilar_claims(tmp_path):
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
        sentence="Romania and China signed the alpha energy deal.",
        event_type="InvestmentProject",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="A completely unrelated gamma cultural festival took place.",
        event_type="InvestmentProject",
    )

    analyzer = CorroborationAnalyzer(semantic_scorer=FakeSemanticScorer())
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    event_groups = results["events"]
    assert len(event_groups) == 2
    assert all(not row["semantically_merged_keys"] for row in event_groups)


def test_semantic_merge_only_compares_within_same_event_type(tmp_path):
    entities_dir, temporals_dir, events_dir = (
        tmp_path / "e",
        tmp_path / "t",
        tmp_path / "v",
    )
    for d in (entities_dir, temporals_dir, events_dir):
        d.mkdir()

    # Identical "alpha" marker (would match), but different event types --
    # must not merge across types even though the fake embedder can't tell.
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-1",
        url="https://www.reuters.com/a",
        sentence="Romania and China signed the alpha energy deal.",
        event_type="InvestmentProject",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="An alpha cultural exchange programme was announced.",
        event_type="CulturalExchange",
    )

    analyzer = CorroborationAnalyzer(semantic_scorer=FakeSemanticScorer())
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    assert len(results["events"]) == 2


def test_disabled_semantic_merge_falls_back_to_exact_signature_only(tmp_path, monkeypatch):
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
        sentence="Romania and China signed the alpha energy deal.",
        event_type="InvestmentProject",
    )
    _write_events_article(
        events_dir,
        entities_dir,
        temporals_dir,
        article_id="art-2",
        url="https://www.bbc.com/b",
        sentence="Bucharest and Beijing finalized the alpha energy agreement.",
        event_type="InvestmentProject",
    )

    analyzer = CorroborationAnalyzer(semantic_scorer=FakeSemanticScorer())
    analyzer._use_semantic_merge = False
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    # With merging off, the two distinct participant sets keep two exact-signature groups.
    assert len(results["events"]) == 2


def _real_scorer_or_skip() -> SemanticSimilarityScorer:
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    scorer = SemanticSimilarityScorer()
    if not scorer.available():
        pytest.skip("semantic similarity model weights unavailable (no network on first run?)")
    return scorer


def test_real_model_scores_paraphrase_higher_than_unrelated_sentence():
    scorer = _real_scorer_or_skip()
    paraphrase_sim = scorer.cosine_similarity(
        scorer.embed("Romania and China signed a new energy investment deal."),
        scorer.embed("Bucharest and Beijing finalized an agreement on energy investment."),
    )
    unrelated_sim = scorer.cosine_similarity(
        scorer.embed("Romania and China signed a new energy investment deal."),
        scorer.embed("A cultural festival took place in Cluj last weekend."),
    )
    assert paraphrase_sim > unrelated_sim
