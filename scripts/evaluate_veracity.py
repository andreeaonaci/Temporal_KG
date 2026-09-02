#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Ablation study for the composite Temporal-Corroboration Veracity Score (TCVS).

For a small set of representative claim profiles (see ``CASES`` below --
covering a strongly-corroborated claim, a single-source claim, a
temporally-contradicted claim, and edge cases in between) this script prints
the full TCVS score alongside the score with each of its three components
(credibility, corroboration, temporal_consistency) individually removed, so
the marginal contribution of each signal to the score and to the label is
visible -- not just asserted. This is the table the paper's "why a composite
score instead of a threshold cascade" section is built from.

Usage:
    python scripts/evaluate_veracity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.veracity_score import VeracityFeatures, VeracityScorer  # noqa: E402

CASES: dict[str, VeracityFeatures] = {
    "strong_corroboration": VeracityFeatures(
        credibility_score=0.85,
        support_count=5,
        source_diversity=3,
        contradiction_flag=False,
        temporal_issue_count=0,
    ),
    "single_source_high_credibility": VeracityFeatures(
        credibility_score=1.0,
        support_count=1,
        source_diversity=1,
        contradiction_flag=False,
        temporal_issue_count=0,
    ),
    "many_sources_low_credibility": VeracityFeatures(
        credibility_score=0.3,
        support_count=4,
        source_diversity=3,
        contradiction_flag=False,
        temporal_issue_count=0,
    ),
    "temporally_contradicted": VeracityFeatures(
        credibility_score=0.9,
        support_count=4,
        source_diversity=3,
        contradiction_flag=False,
        temporal_issue_count=1,
    ),
    "explicit_contradiction": VeracityFeatures(
        credibility_score=0.7,
        support_count=3,
        source_diversity=2,
        contradiction_flag=True,
        temporal_issue_count=0,
    ),
    "unverified_new_claim": VeracityFeatures(
        credibility_score=0.5,
        support_count=0,
        source_diversity=0,
        contradiction_flag=False,
        temporal_issue_count=0,
    ),
}


def main() -> None:
    scorer = VeracityScorer()
    for name, features in CASES.items():
        print(f"--- {name} ---")
        report = scorer.ablation_report(features)
        full = report["full"]
        print(
            f"  full: score={full.score:.3f} label={full.label} "
            f"components={full.components}"
        )
        for key, result in report.items():
            if key == "full":
                continue
            delta = full.score - result.score
            print(
                f"  {key:<26} score={result.score:.3f} label={result.label:<22} "
                f"delta_vs_full={delta:+.3f}"
            )
        print()


if __name__ == "__main__":
    main()
