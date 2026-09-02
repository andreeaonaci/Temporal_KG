#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Mine real candidate corroboration/contradiction pairs from ingested data.

Every gold pair-set so far (corroboration, contradiction, temporal
contradiction) is hand-constructed: real gold-eval-set sentences,
hand-paraphrased or hand-written to be positive/negative examples. That's
fine for threshold calibration, but it's not evidence the semantic merge
actually works on real cross-outlet duplicate reporting -- it's only been
tested on sentences one person wrote to be similar.

This script closes that gap: it runs CorroborationAnalyzer over real
extracted data and pulls out every sentence pair that the semantic merge
actually combined into one corroboration group (support_count >= 2, i.e.
different articles) -- real candidate pairs, unlabeled, ready for blind
human review via label_pairs.py. A human then judges whether the merge was
actually correct, which is the real question: not "does the embedding
model behave sensibly on sentences I wrote to be similar" but "does it
merge what real independent reporting actually produces."

Usage (run after entity/temporal/event extraction has populated
data/exports/{entities,temporals,events}/):
    python scripts/mine_real_candidate_pairs.py \\
        --entities-dir data/exports/entities \\
        --temporals-dir data/exports/temporals \\
        --events-dir data/exports/events \\
        --out data/exports/mined_candidate_pairs.json

Then review them blind:
    python scripts/label_pairs.py --fixture data/exports/mined_candidate_pairs.json \\
        --schema corroboration --annotator <name> --out mined_pairs.<name>.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.corroboration import CorroborationAnalyzer  # noqa: E402
from src.extraction.pipeline_utils import stable_id  # noqa: E402


def mine_pairs(
    entities_dir: Path, temporals_dir: Path, events_dir: Path, *, record_type: str, min_support: int
) -> list[dict[str, Any]]:
    analyzer = CorroborationAnalyzer()
    results = analyzer.analyze_directories(
        entities_dir=entities_dir, temporals_dir=temporals_dir, events_dir=events_dir
    )

    candidates: list[dict[str, Any]] = []
    seen_sentence_pairs: set[tuple[str, str]] = set()
    for group in results.get(record_type, []):
        if group["support_count"] < min_support:
            continue
        sentences = group.get("sample_sentences") or [group["sample_sentence"]]
        if len(sentences) < 2:
            continue
        for sentence_a, sentence_b in itertools.combinations(sentences, 2):
            key = tuple(sorted((sentence_a, sentence_b)))
            if key in seen_sentence_pairs:
                continue
            seen_sentence_pairs.add(key)
            candidates.append(
                {
                    "id": stable_id("mined", record_type, sentence_a, sentence_b),
                    "sentence_a": sentence_a,
                    "sentence_b": sentence_b,
                    "source": {
                        "record_type": record_type,
                        "record_key": group["record_key"],
                        "support_count": group["support_count"],
                        "semantically_merged_keys": group.get("semantically_merged_keys", []),
                        "article_ids": group["article_ids"],
                    },
                }
            )
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mine real candidate corroboration pairs from extracted data for blind human review."
    )
    parser.add_argument("--entities-dir", type=Path, required=True)
    parser.add_argument("--temporals-dir", type=Path, required=True)
    parser.add_argument("--events-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--record-type", choices=["events", "claims"], default="claims")
    parser.add_argument(
        "--min-support", type=int, default=2,
        help="Only mine pairs from groups with at least this many corroborating articles.",
    )
    args = parser.parse_args()

    candidates = mine_pairs(
        args.entities_dir, args.temporals_dir, args.events_dir,
        record_type=args.record_type, min_support=args.min_support,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "_note": (
                    "Unlabeled candidate pairs mined from real extracted data -- "
                    "every pair here is one the semantic merge actually combined "
                    "into a corroboration group. Label with: "
                    "python scripts/label_pairs.py --fixture <this file> "
                    "--schema corroboration --annotator <name> --out <output>"
                ),
                "items": candidates,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Mined {len(candidates)} candidate pairs from real data -> {args.out}")
    if not candidates:
        print(
            "No candidates found -- either the corpus is too small/sparse for the "
            "semantic merge to have combined anything yet, or min_support is too high."
        )


if __name__ == "__main__":
    main()
