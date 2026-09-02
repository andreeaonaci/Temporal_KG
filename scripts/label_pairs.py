#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Blind relabeling CLI for a second annotator, for inter-annotator agreement.

Every gold pair-set in tests/fixtures/ (corroboration, contradiction,
temporal contradiction) has exactly one annotator so far -- whoever wrote
the fixture. That's a real gap: the closest paper in this project's
literature review (ClaimFlow) reports Cohen's kappa=0.77 against a second
human annotator, and any conference-tier submission touching claim
veracity/contradiction is expected to show the same. This script lets a
second person relabel an existing fixture *blind* -- it shows only the
input text, never the original label or reason, so the second judgment is
independent -- and writes a separate output file keyed by item id so
compute_iaa.py can measure agreement against the original.

Resumable: rerunning with the same --out file skips items already labeled
in it, so a labeling session can be split across multiple sittings.

Usage:
    python scripts/label_pairs.py --fixture tests/fixtures/gold_corroboration_pairs.json \\
        --annotator alice --out tests/fixtures/gold_corroboration_pairs.alice.json
    python scripts/label_pairs.py --fixture tests/fixtures/gold_temporal_contradiction_pairs.json \\
        --annotator bob --out tests/fixtures/gold_temporal_contradiction_pairs.bob.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Minimum wall-clock seconds a real answer should take: long enough that no
# human can have read two sentences and judged them, short enough not to
# punish a genuinely fast/easy call. Exists because this exact failure mode
# has happened repeatedly on this project (labeled_at deltas of ~0.15-0.35s
# across dozens/hundreds of consecutive answers, all identical) -- almost
# certainly a held key auto-repeating (OS repeat rate is typically ~150-250ms
# once triggered) or a burst paste, not deliberate per-pair judgment.
# input() has no way to tell a held key apart from N separate keypresses, so
# this timer is the actual defense: an answer faster than this is rejected
# and the same pair is re-shown rather than silently accepted and advanced.
_MIN_SECONDS_PER_ANSWER = 3.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# schema name -> (label field in the original fixture, fields shown to the
# annotator, prompt text). The label field is never displayed -- only used
# to know what key to write the new judgment under, so output files stay
# structurally comparable to the original for compute_iaa.py.
SCHEMAS: dict[str, dict[str, Any]] = {
    "corroboration": {
        "detect_key": "same_claim",
        "display_fields": ["sentence_a", "sentence_b"],
        "label_field": "same_claim",
        "prompt": "Same underlying claim, just worded differently? (y/n, s=skip, q=save&quit): ",
    },
    "contradiction": {
        "detect_key": "contradiction",
        "display_fields": ["sentence_a", "sentence_b"],
        "label_field": "contradiction",
        "prompt": "Do these two sentences contradict each other? (y/n, s=skip, q=save&quit): ",
    },
    "temporal_contradiction": {
        "detect_key": "is_true_contradiction",
        "display_fields": ["sentence_a", "date_a", "sentence_b", "date_b"],
        "label_field": "is_true_contradiction",
        "prompt": (
            "Genuine contradiction -- NOT just sequential lifecycle stages "
            "of the same process? (y/n, s=skip, q=save&quit): "
        ),
    },
}


def _detect_schema(items: list[dict[str, Any]]) -> str:
    if not items:
        raise ValueError("Fixture has no items; can't auto-detect schema.")
    keys = set(items[0])
    for name, schema in SCHEMAS.items():
        if schema["detect_key"] in keys:
            return name
    raise ValueError(
        f"Could not auto-detect schema from fields {sorted(keys)}. "
        f"Pass --schema explicitly: {list(SCHEMAS)}"
    )


def _load_existing(out_path: Path) -> dict[str, Any]:
    if not out_path.exists():
        return {}
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload.get("items", [])}


def _prompt_bool(prompt: str) -> str:
    while True:
        started = time.monotonic()
        response = input(prompt).strip().lower()
        elapsed = time.monotonic() - started

        if response in ("y", "yes", "n", "no", "s", "skip"):
            if elapsed < _MIN_SECONDS_PER_ANSWER:
                # Too fast to be a real read-and-judge -- almost certainly a
                # held/auto-repeating key or a paste burst, not a deliberate
                # answer. Re-show the same prompt instead of recording it;
                # this absorbs a repeat/paste burst harmlessly (it just
                # re-triggers this same check on every extra line) rather
                # than silently accepting invalid data.
                print(
                    f"  That took {elapsed:.2f}s -- too fast to be a real judgment "
                    f"(minimum {_MIN_SECONDS_PER_ANSWER:.0f}s). Not recorded; "
                    "take a moment to actually read both sentences, then answer again."
                )
                continue
        if response in ("y", "yes"):
            return "yes"
        if response in ("n", "no"):
            return "no"
        if response in ("s", "skip"):
            return "skip"
        if response in ("q", "quit"):
            return "quit"
        print("  Please answer y, n, s (skip), or q (save & quit).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind relabeling CLI for a second annotator.")
    parser.add_argument("--fixture", type=Path, required=True, help="Existing gold_*.json to relabel.")
    parser.add_argument("--annotator", required=True, help="Annotator name/id, recorded in the output.")
    parser.add_argument("--out", type=Path, required=True, help="Where to write this annotator's labels.")
    parser.add_argument("--schema", choices=list(SCHEMAS), default=None)
    args = parser.parse_args()

    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    items = payload["items"]
    schema_name = args.schema or _detect_schema(items)
    schema = SCHEMAS[schema_name]

    existing = _load_existing(args.out)
    print(
        f"Schema: {schema_name}  |  {len(items)} items total, "
        f"{len(existing)} already labeled in {args.out}\n"
    )

    labeled = dict(existing)
    quit_early = False
    for item in items:
        if item["id"] in labeled:
            continue
        print("-" * 60)
        print(f"[{item['id']}]")
        for field in schema["display_fields"]:
            print(f"  {field}: {item.get(field)}")
        answer = _prompt_bool(schema["prompt"])
        if answer == "quit":
            quit_early = True
            break
        if answer == "skip":
            continue
        labeled[item["id"]] = {
            "id": item["id"],
            schema["label_field"]: answer == "yes",
            "annotator": args.annotator,
            "labeled_at": datetime.now(timezone.utc).isoformat(),
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "schema": schema_name,
                "source_fixture": str(args.fixture),
                "annotator": args.annotator,
                "items": list(labeled.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {len(labeled)}/{len(items)} labels to {args.out}")
    if quit_early:
        print("Stopped early -- rerun the same command to resume where you left off.")


if __name__ == "__main__":
    main()
