# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Unit tests for the composite Temporal-Corroboration Veracity Score."""

from src.credibility.veracity_score import VeracityFeatures, VeracityScorer


def test_strong_multi_source_evidence_is_corroborated():
    scorer = VeracityScorer()
    result = scorer.score(
        VeracityFeatures(
            credibility_score=0.85,
            support_count=5,
            source_diversity=3,
            contradiction_flag=False,
            temporal_issue_count=0,
        )
    )
    assert result.label == "corroborated"
    assert result.score > 0.9


def test_single_source_cannot_be_labeled_corroborated_even_at_max_credibility():
    """A lone, highly-credible source is not the same thing as corroboration.

    Regression test for the failure mode caught during development: naively
    thresholding the blended score let credibility=1.0 alone push a
    single-source claim over the "corroborated" line.
    """
    scorer = VeracityScorer()
    result = scorer.score(
        VeracityFeatures(
            credibility_score=1.0,
            support_count=1,
            source_diversity=1,
            contradiction_flag=False,
            temporal_issue_count=0,
        )
    )
    assert result.label != "corroborated"


def test_contradiction_flag_overrides_score_to_contested():
    scorer = VeracityScorer()
    result = scorer.score(
        VeracityFeatures(
            credibility_score=0.9,
            support_count=5,
            source_diversity=3,
            contradiction_flag=True,
            temporal_issue_count=0,
        )
    )
    assert result.label == "contested"


def test_temporal_inconsistency_overrides_score_to_contested():
    scorer = VeracityScorer()
    result = scorer.score(
        VeracityFeatures(
            credibility_score=0.9,
            support_count=5,
            source_diversity=3,
            contradiction_flag=False,
            temporal_issue_count=1,
        )
    )
    assert result.label == "contested"


def test_zero_support_is_unverified():
    scorer = VeracityScorer()
    result = scorer.score(
        VeracityFeatures(
            credibility_score=0.5,
            support_count=0,
            source_diversity=0,
            contradiction_flag=False,
            temporal_issue_count=0,
        )
    )
    assert result.label == "unverified"


def test_ablation_report_removes_each_component_exactly_once():
    scorer = VeracityScorer()
    features = VeracityFeatures(
        credibility_score=0.7,
        support_count=3,
        source_diversity=2,
        contradiction_flag=False,
        temporal_issue_count=0,
    )
    report = scorer.ablation_report(features)
    assert set(report) == {
        "full",
        "without_credibility",
        "without_corroboration",
        "without_temporal_consistency",
    }
    # Removing a component should change the score unless that component's
    # signal happened to equal the blend anyway.
    full_score = report["full"].score
    assert any(result.score != full_score for key, result in report.items() if key != "full")


def test_weights_are_renormalized_after_ablation():
    scorer = VeracityScorer()
    features = VeracityFeatures(
        credibility_score=1.0,
        support_count=5,
        source_diversity=3,
        contradiction_flag=False,
        temporal_issue_count=0,
    )
    without_corroboration = scorer.score(features, ablate=frozenset({"corroboration"}))
    assert without_corroboration.weights_used["corroboration"] == 0.0
    assert sum(without_corroboration.weights_used.values()) == 1.0
