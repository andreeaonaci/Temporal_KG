# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

from src.evaluation.metrics import (
    compute_precision_recall_f1,
    compute_temporal_accuracy,
)
from src.evaluation.pipeline import EvaluationPipeline


def test_metric_helpers_compute_expected_scores():
    prf = compute_precision_recall_f1({"a", "b"}, {"b", "c"})
    accuracy = compute_temporal_accuracy(
        {("x", 0): "2025"},
        {("x", 0): "2025"},
    )

    assert prf["precision"] == 0.5
    assert prf["recall"] == 0.5
    assert prf["f1"] == 0.5
    assert accuracy["accuracy"] == 1.0


def test_evaluation_pipeline_builds_summary_and_case_study():
    gold = {
        "entities": {
            "article-1": {
                "entities": [
                    {
                        "canonical_name": "China",
                        "entity_type": "COUNTRY",
                    }
                ]
            }
        },
        "temporals": {
            "article-1": {
                "temporal_expressions": [
                    {
                        "text": "May 2025",
                        "sentence_index": 0,
                        "normalized": "2025-05",
                    }
                ]
            }
        },
        "events": {
            "article-1": {
                "events": [
                    {
                        "event_type": "DiplomaticMeeting",
                        "normalized_trigger": "meeting",
                        "participant_entity_ids": ["china-id"],
                        "temporal_id": "time-1",
                    }
                ]
            }
        },
        "relations": {
            "article-1": {
                "relations": [
                    {
                        "relation_type": "participated_in",
                        "source_id": "china-id",
                        "target_id": "event-1",
                    }
                ]
            }
        },
    }
    predicted = {
        "entities": gold["entities"],
        "temporals": gold["temporals"],
        "events": gold["events"],
        "relations": {"article-1": {"relations": []}},
    }

    report = EvaluationPipeline().evaluate(
        gold_bundle=gold,
        predicted_bundle=predicted,
    )

    assert report["summary"]["entities"]["f1"] == 1.0
    assert report["summary"]["relations"]["recall"] == 0.0
    assert report["per_article"][0]["case_study"]["missing_relations"]
