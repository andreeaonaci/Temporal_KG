#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Precision/recall of semantic corroboration matching against a labeled pair set.

``CorroborationAnalyzer`` used to group claims into corroboration clusters by
an *exact* signature only (event type + participants + date, or the fully
normalized sentence text) -- see ``pipeline_utils.build_event_signature`` /
``build_claim_signature``. Two outlets reporting the same real event in
different words never shared an exact signature and were therefore never
counted as corroborating each other, which silently undercounts the
veracity score's most important input signal.

``SemanticSimilarityScorer`` (src/credibility/semantic_similarity.py) adds a
second, embedding-similarity matching layer on top of the exact one. This
script answers the question that matters before trusting that layer: at the
configured cosine-similarity threshold, does it actually distinguish
"same claim, different words" from "different claim, same topic" -- or does
it just merge anything topically related?

``LexicalOverlapScorer`` (src/credibility/lexical_similarity.py) adds the
other side of the comparison this ablation was missing: the standard
bag-of-words baseline from fact-checking literature (see Lendvai & Reichel
2016's lexical-overlap contradiction features). Every number this project
has reported for semantic matching so far was self-ablation (embeddings on
vs. off) -- ``--compare`` runs both scorers on the same pairs so "beats a
real prior-art-style baseline" is an actual claim, not an assumption.

Usage:
    python scripts/evaluate_corroboration.py
    python scripts/evaluate_corroboration.py --pairs tests/fixtures/gold_corroboration_pairs.json
    python scripts/evaluate_corroboration.py --sweep   # precision/recall at several thresholds
    python scripts/evaluate_corroboration.py --baseline lexical   # run the Jaccard baseline instead
    python scripts/evaluate_corroboration.py --compare  # semantic vs. lexical, side by side
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

from src.credibility.lexical_similarity import LexicalOverlapScorer  # noqa: E402
from src.credibility.semantic_similarity import SemanticSimilarityScorer  # noqa: E402

DEFAULT_PAIRS = PROJECT_ROOT / "tests" / "fixtures" / "gold_corroboration_pairs.json"
SWEEP_THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


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
    scorer: SemanticSimilarityScorer,
    threshold: float,
) -> tuple[PRF, list[dict[str, Any]]]:
    prf = PRF()
    rows: list[dict[str, Any]] = []
    for item in items:
        emb_a = scorer.embed(item["sentence_a"])
        emb_b = scorer.embed(item["sentence_b"])
        similarity = scorer.cosine_similarity(emb_a, emb_b)
        predicted = similarity >= threshold
        gold = bool(item["same_claim"])

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
                "similarity": round(similarity, 3),
                "gold": gold,
                "predicted": predicted,
                "correct": predicted == gold,
            }
        )
    return prf, rows


def _make_scorer(name: str):
    return LexicalOverlapScorer() if name == "lexical" else SemanticSimilarityScorer()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate semantic corroboration matching against labeled sentence pairs."
    )
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--sweep", action="store_true", help="Report P/R/F1 across several thresholds.")
    parser.add_argument(
        "--baseline", choices=["semantic", "lexical"], default="semantic",
        help="Which scorer to evaluate: the embedding model (default) or the Jaccard baseline.",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Run both semantic and lexical scorers on the same pairs and print them side by side.",
    )
    args = parser.parse_args()

    items = _load_pairs(args.pairs)
    print(f"Loaded {len(items)} labeled pairs from {args.pairs}\n")

    if args.compare:
        print(f"{'scorer':>10}  {'P':>6}  {'R':>6}  {'F1':>6}  {'acc':>6}")
        for name in ("lexical", "semantic"):
            scorer = _make_scorer(name)
            if not scorer.available():
                print(f"{name:>10}  (unavailable in this environment)")
                continue
            prf, _ = _score_pairs(items, scorer, scorer.threshold)
            print(
                f"{name:>10}  {prf.precision:>6.3f}  {prf.recall:>6.3f}  "
                f"{prf.f1:>6.3f}  {prf.accuracy:>6.3f}"
            )
        return

    scorer = _make_scorer(args.baseline)
    if not scorer.available():
        print(
            "Semantic similarity model unavailable in this environment "
            "(transformers/torch missing or model download failed) -- "
            "corroboration matching would silently fall back to "
            "exact-signature-only. Install transformers+torch and retry."
        )
        return

    if args.sweep:
        print(f"{'threshold':>10}  {'P':>6}  {'R':>6}  {'F1':>6}  {'acc':>6}")
        for threshold in SWEEP_THRESHOLDS:
            prf, _ = _score_pairs(items, scorer, threshold)
            print(
                f"{threshold:>10.2f}  {prf.precision:>6.3f}  {prf.recall:>6.3f}  "
                f"{prf.f1:>6.3f}  {prf.accuracy:>6.3f}"
            )
        print(
            "\nConfigured default is credibility.semantic_similarity.threshold "
            f"(currently {scorer.threshold}) -- pick the row that matches your "
            "precision/recall priority and update settings.yaml if it differs."
        )
        return

    prf, rows = _score_pairs(items, scorer, scorer.threshold)
    print(f"=== {args.baseline} corroboration matching (threshold={scorer.threshold}) ===")
    print(
        f"P={prf.precision:.3f}  R={prf.recall:.3f}  F1={prf.f1:.3f}  "
        f"acc={prf.accuracy:.3f}  (tp={prf.tp} fp={prf.fp} fn={prf.fn} tn={prf.tn})\n"
    )
    for row in rows:
        mark = "OK " if row["correct"] else "ERR"
        print(
            f"[{mark}] {row['id']:<10} sim={row['similarity']:.3f}  "
            f"gold={row['gold']!s:<5} predicted={row['predicted']!s:<5}"
        )


if __name__ == "__main__":
    main()
