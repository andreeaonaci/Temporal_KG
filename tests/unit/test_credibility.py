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


def test_state_affiliated_domain_scores_between_default_and_reliable():
    from src.credibility.scorer import CredibilityScorer
    scorer = CredibilityScorer()
    score = scorer.score_url("https://www.chinadaily.com.cn/some/article")
    assert scorer._default < score < 1.0
    assert score == scorer._state_affiliated_score


def test_state_affiliated_domain_is_not_scored_as_fully_reliable():
    from src.credibility.scorer import CredibilityScorer
    scorer = CredibilityScorer()
    assert scorer.score_url("https://radio.cgtn.com/some/article") != 1.0


def test_www_prefix_is_stripped_as_exact_prefix_not_charset(monkeypatch):
    # Regression test for the lstrip("www.") bug: lstrip strips any leading
    # characters found in the given set ({'w', '.'}), not the literal
    # substring "www." -- a domain that happens to start with "w" right
    # after "www." would get over-stripped under the old implementation.
    from src.credibility.scorer import CredibilityScorer

    monkeypatch.setattr(
        "src.credibility.scorer.settings",
        lambda key, default=None: (
            ["wano.com"] if key == "credibility.known_reliable_domains" else default
        ),
    )
    scorer = CredibilityScorer()
    # "www.wano.com" must resolve to reliable domain "wano.com", not get
    # mangled into "ano.com" by an overzealous charset strip.
    assert scorer.score_url("https://www.wano.com/article") == 1.0
