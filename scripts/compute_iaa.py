#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Cohen's kappa between two label sets for the same items.

Compares the original gold_*.json fixture (the first annotator) against a
second annotator's output from label_pairs.py, on whichever binary label
field the fixture's schema uses. No external stats dependency -- Cohen's
kappa for a 2x2 table is simple enough to compute directly:

    kappa = (po - pe) / (1 - pe)

where po is observed agreement and pe is the agreement expected by chance
given each annotator's marginal label distribution.

Usage:
    python scripts/compute_iaa.py \\
        --fixture tests/fixtures/gold_corroboration_pairs.json \\
        --second tests/fixtures/gold_corroboration_pairs.alice.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.label_pairs import SCHEMAS, _detect_schema  # noqa: E402


def _load_labels(path: Path, label_field: str) -> dict[str, bool]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload["items"]
    return {item["id"]: bool(item[label_field]) for item in items if label_field in item}


def cohens_kappa(a: dict[str, bool], b: dict[str, bool]) -> dict[str, Any]:
    shared_ids = sorted(set(a) & set(b))
    n = len(shared_ids)
    if n == 0:
        raise ValueError("No overlapping item ids between the two label sets.")

    agreements = sum(1 for i in shared_ids if a[i] == b[i])
    po = agreements / n

    a_true_rate = sum(1 for i in shared_ids if a[i]) / n
    b_true_rate = sum(1 for i in shared_ids if b[i]) / n
    pe = (a_true_rate * b_true_rate) + ((1 - a_true_rate) * (1 - b_true_rate))

    kappa = (po - pe) / (1 - pe) if pe < 1.0 else 1.0

    disagreements = [
        {"id": i, "annotator_1": a[i], "annotator_2": b[i]} for i in shared_ids if a[i] != b[i]
    ]
    return {
        "n_shared": n,
        "observed_agreement": round(po, 4),
        "expected_agreement": round(pe, 4),
        "cohens_kappa": round(kappa, 4),
        "disagreements": disagreements,
    }


def _interpret(kappa: float) -> str:
    # Landis & Koch (1977) benchmark, the standard reference scale for this.
    if kappa < 0:
        return "poor (worse than chance)"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


def main() -> None:
    parser = argparse.ArgumentParser(description="Cohen's kappa between two annotators' labels.")
    parser.add_argument("--fixture", type=Path, required=True, help="Original gold_*.json (annotator 1).")
    parser.add_argument("--second", type=Path, required=True, help="label_pairs.py output (annotator 2).")
    parser.add_argument("--schema", choices=list(SCHEMAS), default=None)
    args = parser.parse_args()

    fixture_payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    schema_name = args.schema or _detect_schema(fixture_payload["items"])
    label_field = SCHEMAS[schema_name]["label_field"]

    annotator_1 = _load_labels(args.fixture, label_field)
    annotator_2 = _load_labels(args.second, label_field)

    result = cohens_kappa(annotator_1, annotator_2)

    print(f"Schema: {schema_name}  |  label field: {label_field}")
    print(f"Shared items: {result['n_shared']}")
    print(f"Observed agreement: {result['observed_agreement']:.3f}")
    print(f"Expected agreement (chance): {result['expected_agreement']:.3f}")
    print(f"Cohen's kappa: {result['cohens_kappa']:.3f}  ({_interpret(result['cohens_kappa'])})")
    if result["disagreements"]:
        print(f"\nDisagreements ({len(result['disagreements'])}):")
        for d in result["disagreements"]:
            print(f"  [{d['id']}] annotator_1={d['annotator_1']}  annotator_2={d['annotator_2']}")
    else:
        print("\nNo disagreements.")


if __name__ == "__main__":
    main()
