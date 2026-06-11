# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Unit tests for src.credibility.scorer."""


def test_reliable_domain():
    from src.credibility.scorer import CredibilityScorer
    scorer = CredibilityScorer()
    assert scorer.score_url("https://www.reuters.com/world/china/...") == 1.0


def test_unknown_domain_returns_default():
    from src.credibility.scorer import CredibilityScorer
    scorer = CredibilityScorer()
    score = scorer.score_url("https://unknown-blog.example.com/article")
    assert 0.0 <= score <= 1.0


def test_empty_url_returns_default():
    from src.credibility.scorer import CredibilityScorer
    scorer = CredibilityScorer()
    assert scorer.score_url("") == scorer._default
