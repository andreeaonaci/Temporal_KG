#!/usr/bin/env python3
"""Run corroboration and credibility analysis over extracted outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.corroboration import CorroborationAnalyzer  # noqa: E402
from src.utils.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze event and claim corroboration."
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
        "--output-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "credibility",
    )
    args = parser.parse_args()

    analyzer = CorroborationAnalyzer()
    results = analyzer.analyze_directories(
        entities_dir=args.entities_dir,
        temporals_dir=args.temporals_dir,
        events_dir=args.events_dir,
    )
    paths = analyzer.write_results(results, output_dir=args.output_dir)
    print(
        json.dumps(
            {key: str(value) for key, value in paths.items()},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
