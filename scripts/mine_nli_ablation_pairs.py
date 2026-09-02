#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Mine a large, real pairwise pool for the NLI-contradiction-detection
ablation: all distinct-sentence pairs within real (already-merged)
corroboration groups, with the actual NLI contradiction score computed for
each -- both flagged (score >= threshold) and unflagged pairs, not just
hand-picked positives.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.contradiction_nli import ContradictionDetector  # noqa: E402
from src.extraction.pipeline_utils import stable_id  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claims", type=Path, default=Path("data/exports/credibility/corroboration.claims.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    detector = ContradictionDetector()
    print(f"model available: {detector.available()}  threshold: {detector.threshold}")

    pairs = []
    for group in claims:
        sentences = sorted(set(group.get("sample_sentences", [])))
        if len(sentences) < 2:
            continue
        for a, b in itertools.combinations(sentences, 2):
            score = detector.contradiction_score(a, b)
            pairs.append({
                "id": stable_id("nli_ablation", group["record_key"], a, b),
                "record_key": group["record_key"],
                "sentence_a": a[:500],
                "sentence_b": b[:500],
                "nli_score": score,
                "predicted_contradiction": score >= detector.threshold,
            })

    pairs.sort(key=lambda p: p["nli_score"], reverse=True)
    n_pos = sum(1 for p in pairs if p["predicted_contradiction"])
    print(f"Mined {len(pairs)} real within-group sentence pairs. {n_pos} predicted-contradiction, {len(pairs)-n_pos} not.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
