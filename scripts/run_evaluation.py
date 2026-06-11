#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Run the evaluation pipeline against a gold subset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.gold_loader import GoldDataLoader  # noqa: E402
from src.evaluation.pipeline import EvaluationPipeline  # noqa: E402
from src.evaluation.report_generator import ReportGenerator  # noqa: E402
from src.utils.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run extraction evaluation.")
    parser.add_argument(
        "--gold-base-dir",
        type=Path,
        default=settings.project_root / "data" / "gold",
    )
    parser.add_argument(
        "--predicted-base-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "evaluation",
    )
    args = parser.parse_args()

    loader = GoldDataLoader()
    gold_bundle = loader.load_bundle(
        entities_dir=args.gold_base_dir / "entities",
        temporals_dir=args.gold_base_dir / "temporals",
        events_dir=args.gold_base_dir / "events",
        relations_dir=args.gold_base_dir / "relations",
    )
    predicted_bundle = loader.load_bundle(
        entities_dir=args.predicted_base_dir / "entities",
        temporals_dir=args.predicted_base_dir / "temporals",
        events_dir=args.predicted_base_dir / "events",
        relations_dir=args.predicted_base_dir / "relations",
    )
    report = EvaluationPipeline().evaluate(
        gold_bundle=gold_bundle,
        predicted_bundle=predicted_bundle,
    )
    paths = ReportGenerator().write(report, output_dir=args.output_dir)
    print(
        json.dumps(
            {key: str(value) for key, value in paths.items()},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
