# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

import pytest

from scripts.compute_iaa import cohens_kappa


def test_perfect_agreement_gives_kappa_one():
    a = {"1": True, "2": False, "3": True, "4": False}
    b = {"1": True, "2": False, "3": True, "4": False}
    result = cohens_kappa(a, b)
    assert result["observed_agreement"] == 1.0
    assert result["cohens_kappa"] == 1.0
    assert result["disagreements"] == []


def test_chance_level_agreement_gives_kappa_near_zero():
    # Both annotators say True exactly half the time, agreeing only as
    # often as flipping independent coins would predict.
    a = {"1": True, "2": True, "3": False, "4": False}
    b = {"1": True, "2": False, "3": True, "4": False}
    result = cohens_kappa(a, b)
    assert result["observed_agreement"] == 0.5
    assert result["expected_agreement"] == 0.5
    assert result["cohens_kappa"] == 0.0


def test_disagreements_are_reported_with_both_labels():
    a = {"1": True, "2": False}
    b = {"1": False, "2": False}
    result = cohens_kappa(a, b)
    assert result["disagreements"] == [
        {"id": "1", "annotator_1": True, "annotator_2": False}
    ]


def test_only_shared_ids_are_compared():
    a = {"1": True, "2": False, "extra_in_a": True}
    b = {"1": True, "2": False, "extra_in_b": False}
    result = cohens_kappa(a, b)
    assert result["n_shared"] == 2
    assert result["cohens_kappa"] == 1.0


def test_raises_when_no_overlap():
    with pytest.raises(ValueError):
        cohens_kappa({"1": True}, {"2": True})
