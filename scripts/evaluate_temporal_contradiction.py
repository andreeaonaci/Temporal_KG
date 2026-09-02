#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Ablation: naive NLI-only contradiction detection vs. temporal-gated.

A pretrained NLI model flags "the deal was proposed" and "the deal was
signed" as a contradiction, because as isolated sentences they do disagree.
But if the two claims' extracted event dates are sequential (an Allen
before/after/meets/met_by relation), they're describing different stages of
the same real-world process -- claim evolution, not a genuine
contradiction. Only when the two dates are temporally coincident (any other
Allen relation) are both reports actually describing the same instant, so
disagreement between them is a real contradiction.

This script quantifies the difference: on the same pair set, how often does
naive NLI-only detection over-flag legitimate claim evolution as
contradiction, and does gating on the Allen relation between the two events'
extracted dates (src/temporal/reasoner.py) fix it without losing recall on
genuine contradictions?

It also compares against a rule-based reproduction of the core idea behind
Allein et al. (EACL 2023) -- gating on coarse time-bucket distance instead
of the exact Allen relation (src/temporal/time_bucket_gate.py) -- to answer
the fair question a reviewer familiar with that paper would ask: does full
interval-algebra precision actually earn its complexity over just asking
"are these two dates close together"?

Usage:
    python scripts/evaluate_temporal_contradiction.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.contradiction_nli import ContradictionDetector  # noqa: E402
from src.credibility.semantic_similarity import SemanticSimilarityScorer  # noqa: E402
from src.temporal.reasoner import compare_ranges  # noqa: E402
from src.temporal.time_bucket_gate import is_temporally_close  # noqa: E402

DEFAULT_PAIRS = PROJECT_ROOT / "tests" / "fixtures" / "gold_temporal_contradiction_pairs.json"
_TEMPORALLY_SEQUENTIAL_RELATIONS = frozenset({"before", "after", "meets", "met_by"})


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        total = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.tn) / total if total else 0.0


def _load_pairs(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def _score(items, detector, relevance_gate, *, use_temporal_gate: bool, min_relevance: float):
    prf = PRF()
    rows = []
    for item in items:
        relevance = relevance_gate.cosine_similarity(
            relevance_gate.embed(item["sentence_a"]), relevance_gate.embed(item["sentence_b"])
        )
        nli_contradiction = (
            relevance >= min_relevance
            and detector.is_contradiction(item["sentence_a"], item["sentence_b"])
        )

        predicted = nli_contradiction
        allen = None
        if nli_contradiction and use_temporal_gate:
            # end_a/end_b default to the start date itself for the original
            # point-only pairs (date_a == end_a implicitly); interval_00X
            # pairs supply a real end date, exercising Allen relations
            # (contains/during/overlaps/...) a point-only comparison can't.
            allen = compare_ranges(
                item["date_a"], item.get("end_a", item["date_a"]),
                item["date_b"], item.get("end_b", item["date_b"]),
            )
            if allen in _TEMPORALLY_SEQUENTIAL_RELATIONS:
                predicted = False  # reclassified as claim evolution

        gold = bool(item["is_true_contradiction"])
        if predicted and gold:
            prf.tp += 1
        elif predicted and not gold:
            prf.fp += 1
        elif not predicted and gold:
            prf.fn += 1
        else:
            prf.tn += 1

        rows.append(
            {
                "id": item["id"],
                "nli_contradiction": nli_contradiction,
                "allen_relation": allen,
                "predicted": predicted,
                "gold": gold,
                "correct": predicted == gold,
            }
        )
    return prf, rows


def _score_time_bucket_gate(items, detector, relevance_gate, *, min_relevance: float, within: str = "same_day"):
    """Same pipeline as _score, but gates on coarse time-bucket distance
    (Allein et al.-style) instead of the exact Allen relation. "same_day" is
    the fair like-for-like threshold here: every pair in this fixture uses
    point dates (no real intervals), so Allen's "equals" -- the only
    genuinely temporally-coincident relation possible for two points -- is
    exactly "same date," which is what within="same_day" also captures.
    """
    prf = PRF()
    rows = []
    for item in items:
        relevance = relevance_gate.cosine_similarity(
            relevance_gate.embed(item["sentence_a"]), relevance_gate.embed(item["sentence_b"])
        )
        nli_contradiction = (
            relevance >= min_relevance
            and detector.is_contradiction(item["sentence_a"], item["sentence_b"])
        )

        predicted = nli_contradiction
        bucket_close = None
        if nli_contradiction:
            bucket_close = is_temporally_close(item["date_a"], item["date_b"], within=within)
            if not bucket_close:
                predicted = False  # reclassified as claim evolution (dates far apart)

        gold = bool(item["is_true_contradiction"])
        if predicted and gold:
            prf.tp += 1
        elif predicted and not gold:
            prf.fp += 1
        elif not predicted and gold:
            prf.fn += 1
        else:
            prf.tn += 1

        rows.append(
            {
                "id": item["id"],
                "nli_contradiction": nli_contradiction,
                "temporally_close": bucket_close,
                "predicted": predicted,
                "gold": gold,
                "correct": predicted == gold,
            }
        )
    return prf, rows


def _score_date_mismatch_baseline(items):
    """Naive metadata-only baseline: predicted=contradiction iff the two
    dates differ at all, regardless of content. This is roughly what a
    system without NLI does (and what this project's own structural
    contradiction_flag used to do before the semantic/temporal-gated check
    replaced it) -- the strawman both NLI-only and NLI+temporal-gate should
    beat, not just "any signal at all vs. none"."""
    prf = PRF()
    rows = []
    for item in items:
        predicted = item["date_a"] != item["date_b"]
        gold = bool(item["is_true_contradiction"])
        if predicted and gold:
            prf.tp += 1
        elif predicted and not gold:
            prf.fp += 1
        elif not predicted and gold:
            prf.fn += 1
        else:
            prf.tn += 1
        rows.append({"id": item["id"], "predicted": predicted, "gold": gold, "correct": predicted == gold})
    return prf, rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ablate naive NLI-only vs. temporal-gated contradiction detection."
    )
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    args = parser.parse_args()

    items = _load_pairs(args.pairs)
    print(f"Loaded {len(items)} labeled pairs from {args.pairs}\n")

    detector = ContradictionDetector()
    relevance_gate = SemanticSimilarityScorer()
    if not detector.available() or not relevance_gate.available():
        print(
            "NLI/embedding models unavailable in this environment -- "
            "install transformers+torch and retry."
        )
        return
    min_relevance = 0.15

    baseline_prf, _ = _score_date_mismatch_baseline(items)
    print("=== naive date-mismatch-only baseline (no NLI, no gate) ===")
    print(
        f"P={baseline_prf.precision:.3f}  R={baseline_prf.recall:.3f}  F1={baseline_prf.f1:.3f}  "
        f"acc={baseline_prf.accuracy:.3f}  (tp={baseline_prf.tp} fp={baseline_prf.fp} "
        f"fn={baseline_prf.fn} tn={baseline_prf.tn})\n"
    )

    for label, use_gate in (("naive NLI-only (no temporal gate)", False), ("NLI + temporal gate", True)):
        prf, rows = _score(
            items, detector, relevance_gate, use_temporal_gate=use_gate, min_relevance=min_relevance
        )
        print(f"=== {label} ===")
        print(
            f"P={prf.precision:.3f}  R={prf.recall:.3f}  F1={prf.f1:.3f}  "
            f"acc={prf.accuracy:.3f}  (tp={prf.tp} fp={prf.fp} fn={prf.fn} tn={prf.tn})\n"
        )
        for row in rows:
            mark = "OK " if row["correct"] else "ERR"
            relation_note = f"  allen={row['allen_relation']}" if row["allen_relation"] else ""
            print(
                f"[{mark}] {row['id']:<12} nli={row['nli_contradiction']!s:<5} "
                f"predicted={row['predicted']!s:<5} gold={row['gold']!s:<5}{relation_note}"
            )
        print()

    bucket_prf, bucket_rows = _score_time_bucket_gate(
        items, detector, relevance_gate, min_relevance=min_relevance, within="same_day"
    )
    print("=== NLI + coarse time-bucket gate (Allein et al.-style reproduction, within=same_day) ===")
    print(
        f"P={bucket_prf.precision:.3f}  R={bucket_prf.recall:.3f}  F1={bucket_prf.f1:.3f}  "
        f"acc={bucket_prf.accuracy:.3f}  (tp={bucket_prf.tp} fp={bucket_prf.fp} "
        f"fn={bucket_prf.fn} tn={bucket_prf.tn})\n"
    )
    for row in bucket_rows:
        mark = "OK " if row["correct"] else "ERR"
        close_note = f"  close={row['temporally_close']}" if row["temporally_close"] is not None else ""
        print(
            f"[{mark}] {row['id']:<12} nli={row['nli_contradiction']!s:<5} "
            f"predicted={row['predicted']!s:<5} gold={row['gold']!s:<5}{close_note}"
        )
    print()


if __name__ == "__main__":
    main()
