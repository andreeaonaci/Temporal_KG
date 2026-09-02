#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Precision/recall of NLI contradiction detection against a labeled pair set.

``CorroborationAnalyzer``'s contradiction flag used to be purely structural:
it only fired when the extraction pipeline had tagged members of the same
corroboration group with more than one event type or date window. That is
blind to two reports that land in the same group -- correctly, since
they're about the same event -- while stating incompatible facts within it
("12 injured" vs. "2 injured", "signed" vs. "collapsed"). ``ContradictionDetector``
(src/credibility/contradiction_nli.py) adds a pairwise NLI check for that
case. This script answers the question that matters before trusting it:
does it actually catch factual contradiction, without flagging paraphrases
or unrelated-but-topically-similar claims as contradictory?

Raw NLI models trained on MNLI-style data rarely see genuinely off-topic
hypothesis pairs during training, so they can miscode two *unrelated*
sentences as "contradiction" rather than the "neutral" a human would pick
(see the ``contra_009`` sanity-check pair in the fixture -- unrelated
topics, but a raw model call scores it as a confident contradiction).
``CorroborationAnalyzer._detect_semantic_contradiction`` never actually hits
this failure mode, because it only compares sentences already inside one
corroboration group (same event type, same exact/semantic-merged
signature) -- but to make that concrete rather than just asserted, ``--gate``
reproduces the same embedding-similarity pre-filter here so you can see the
before/after on the same fixture.

Usage:
    python scripts/evaluate_contradiction.py
    python scripts/evaluate_contradiction.py --sweep
    python scripts/evaluate_contradiction.py --gate   # with the production relevance pre-filter
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
from src.utils.config import settings  # noqa: E402

DEFAULT_PAIRS = PROJECT_ROOT / "tests" / "fixtures" / "gold_contradiction_pairs.json"
SWEEP_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


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
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["items"]


def _score_pairs(
    items: list[dict[str, Any]],
    detector: ContradictionDetector,
    threshold: float,
    *,
    relevance_gate: SemanticSimilarityScorer | None = None,
    min_relevance: float = 0.15,
) -> tuple[PRF, list[dict[str, Any]]]:
    prf = PRF()
    rows: list[dict[str, Any]] = []
    for item in items:
        gated = False
        if relevance_gate is not None and relevance_gate.available():
            relevance = relevance_gate.cosine_similarity(
                relevance_gate.embed(item["sentence_a"]),
                relevance_gate.embed(item["sentence_b"]),
            )
            if relevance < min_relevance:
                gated = True

        score = 0.0 if gated else detector.contradiction_score(
            item["sentence_a"], item["sentence_b"]
        )
        predicted = score >= threshold
        gold = bool(item["contradiction"])

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
                "score": round(score, 3),
                "gold": gold,
                "predicted": predicted,
                "correct": predicted == gold,
                "gated": gated,
            }
        )
    return prf, rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate NLI contradiction detection against labeled sentence pairs."
    )
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--sweep", action="store_true", help="Report P/R/F1 across several thresholds.")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Apply the same embedding-similarity relevance pre-filter the production "
        "pipeline uses, so unrelated-topic pairs never reach the NLI call.",
    )
    args = parser.parse_args()

    items = _load_pairs(args.pairs)
    print(f"Loaded {len(items)} labeled pairs from {args.pairs}\n")

    detector = ContradictionDetector()
    if not detector.available():
        print(
            "Contradiction NLI model unavailable in this environment "
            "(transformers/torch missing or model download failed) -- "
            "corroboration would silently fall back to structural-only "
            "contradiction detection. Install transformers+torch and retry."
        )
        return

    relevance_gate = None
    min_relevance = float(
        settings("credibility.contradiction_nli.min_relevance_similarity", 0.15)
    )
    if args.gate:
        relevance_gate = SemanticSimilarityScorer()
        if not relevance_gate.available():
            print(
                "--gate requested but the embedding model is unavailable; "
                "running without the relevance pre-filter.\n"
            )
            relevance_gate = None

    if args.sweep:
        print(f"{'threshold':>10}  {'P':>6}  {'R':>6}  {'F1':>6}  {'acc':>6}")
        for threshold in SWEEP_THRESHOLDS:
            prf, _ = _score_pairs(
                items,
                detector,
                threshold,
                relevance_gate=relevance_gate,
                min_relevance=min_relevance,
            )
            print(
                f"{threshold:>10.2f}  {prf.precision:>6.3f}  {prf.recall:>6.3f}  "
                f"{prf.f1:>6.3f}  {prf.accuracy:>6.3f}"
            )
        print(
            "\nConfigured default is credibility.contradiction_nli.threshold "
            f"(currently {detector.threshold}) -- pick the row that matches your "
            "precision/recall priority and update settings.yaml if it differs."
        )
        return

    prf, rows = _score_pairs(
        items,
        detector,
        detector.threshold,
        relevance_gate=relevance_gate,
        min_relevance=min_relevance,
    )
    gate_label = " + relevance gate" if relevance_gate is not None else ""
    print(f"=== NLI contradiction detection (threshold={detector.threshold}{gate_label}) ===")
    print(
        f"P={prf.precision:.3f}  R={prf.recall:.3f}  F1={prf.f1:.3f}  "
        f"acc={prf.accuracy:.3f}  (tp={prf.tp} fp={prf.fp} fn={prf.fn} tn={prf.tn})\n"
    )
    for row in rows:
        mark = "OK " if row["correct"] else "ERR"
        gate_note = " [gated: below relevance threshold]" if row["gated"] else ""
        print(
            f"[{mark}] {row['id']:<12} score={row['score']:.3f}  "
            f"gold={row['gold']!s:<5} predicted={row['predicted']!s:<5}{gate_note}"
        )


if __name__ == "__main__":
    main()
