#!/usr/bin/env python3
"""Run claim verification heuristics over extracted outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.fake_news import ClaimVerifier  # noqa: E402
from src.utils.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assess claims for corroboration and temporal consistency."
    )
    parser.add_argument(
        "--entities-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "entities",
    )
    parser.add_argument(
        "--temporals-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "temporals",
    )
    parser.add_argument(
        "--events-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "events",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "credibility" / "claim_assessments.json",
    )
    args = parser.parse_args()

    verifier = ClaimVerifier()
    assessments = verifier.assess(
        entities_dir=args.entities_dir,
        temporals_dir=args.temporals_dir,
        events_dir=args.events_dir,
    )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps([a.__dict__ for a in assessments], indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(assessments)} assessments to {args.output_path}")


if __name__ == "__main__":
    main()
