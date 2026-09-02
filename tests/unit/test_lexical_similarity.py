# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

from src.credibility.lexical_similarity import LexicalOverlapScorer


def test_identical_text_has_similarity_one():
    scorer = LexicalOverlapScorer()
    a = scorer.embed("Romania and China signed an energy deal")
    b = scorer.embed("Romania and China signed an energy deal")
    assert scorer.cosine_similarity(a, b) == 1.0


def test_disjoint_text_has_similarity_zero():
    scorer = LexicalOverlapScorer()
    a = scorer.embed("Romania and China signed an energy deal")
    b = scorer.embed("A festival was held in Cluj last weekend")
    assert scorer.cosine_similarity(a, b) == 0.0


def test_partial_overlap_is_between_zero_and_one():
    scorer = LexicalOverlapScorer()
    a = scorer.embed("Romania and China signed an energy deal")
    b = scorer.embed("Romania and China discussed an energy partnership")
    similarity = scorer.cosine_similarity(a, b)
    assert 0.0 < similarity < 1.0


def test_is_match_respects_threshold():
    scorer = LexicalOverlapScorer()
    scorer.threshold = 0.5
    identical = scorer.embed("same text here")
    assert scorer.is_match(identical, scorer.embed("same text here")) is True
    assert scorer.is_match(identical, scorer.embed("completely different words")) is False


def test_empty_text_never_matches():
    scorer = LexicalOverlapScorer()
    assert scorer.cosine_similarity(scorer.embed(""), scorer.embed("something")) == 0.0
    assert scorer.cosine_similarity(scorer.embed(""), scorer.embed("")) == 0.0


def test_paraphrase_pair_from_gold_set_beats_hard_negative():
    # Same regression the semantic scorer was validated against, but for
    # the lexical baseline: the paraphrase pair should score higher than
    # the unrelated pair, even though its absolute score is much lower
    # than the embedding model's (no shared surface words for a good
    # paraphrase means low Jaccard despite being the same claim).
    scorer = LexicalOverlapScorer()
    paraphrase_sim = scorer.cosine_similarity(
        scorer.embed("Romania and China signed a new energy investment deal."),
        scorer.embed("Bucharest and Beijing finalized an agreement on energy investment."),
    )
    unrelated_sim = scorer.cosine_similarity(
        scorer.embed("Romania and China signed a new energy investment deal."),
        scorer.embed("A cultural festival took place in Cluj last weekend."),
    )
    assert paraphrase_sim >= unrelated_sim
