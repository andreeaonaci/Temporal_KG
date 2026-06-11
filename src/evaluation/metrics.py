# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Metric utilities for extraction and graph evaluation."""

from __future__ import annotations

from typing import Any, Iterable


def compute_precision_recall_f1(
    predicted: Iterable[Any],
    gold: Iterable[Any],
) -> dict[str, float]:
    """Compute exact-match precision, recall, and F1."""
    predicted_set = set(predicted)
    gold_set = set(gold)
    true_positive = len(predicted_set & gold_set)
    precision = true_positive / len(predicted_set) if predicted_set else 0.0
    recall = true_positive / len(gold_set) if gold_set else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positive": true_positive,
        "predicted_total": len(predicted_set),
        "gold_total": len(gold_set),
    }


def compute_temporal_accuracy(
    predicted: dict[tuple[Any, ...], Any],
    gold: dict[tuple[Any, ...], Any],
) -> dict[str, float]:
    """Compute exact-match accuracy for normalized temporal values."""
    if not gold:
        return {"accuracy": 0.0, "correct": 0, "total": 0}
    correct = 0
    for key, gold_value in gold.items():
        if predicted.get(key) == gold_value:
            correct += 1
    return {
        "accuracy": round(correct / len(gold), 4),
        "correct": correct,
        "total": len(gold),
    }
