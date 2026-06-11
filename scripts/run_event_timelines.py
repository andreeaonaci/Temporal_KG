#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Run event timeline queries and print table summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.query_layer import TemporalGraphQueries  # noqa: E402
from src.reporting.helpers import chart_event_type_distribution  # noqa: E402
from src.utils.config import settings  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query Neo4j events and summarize timeline/activity outputs."
    )
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-12-31")
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional JSON output path for all computed summaries.",
    )
    args = parser.parse_args()

    # Debug: Show what Neo4j URI is being used
    neo4j_uri = settings("database.neo4j_uri")
    neo4j_user = settings("database.neo4j_user")
    log.info(f"Neo4j URI: {neo4j_uri}")
    log.info(f"Neo4j User: {neo4j_user}")

    queries = TemporalGraphQueries()
    events = queries.events_within_date_range(
        start_date=args.start_date,
        end_date=args.end_date,
    )
    event_type_counts = chart_event_type_distribution(events).to_dict()
    bilateral_timeline = queries.bilateral_activity_timeline(
        start_date=args.start_date,
        end_date=args.end_date,
    )

    print(f"Fetched {len(events)} event(s)")
    print("\nEvent type distribution:")
    print(json.dumps(event_type_counts, indent=2, ensure_ascii=False))
    print("\nBilateral timeline:")
    print(json.dumps(bilateral_timeline, indent=2, ensure_ascii=False))

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(
                {
                    "event_count": len(events),
                    "event_type_distribution": event_type_counts,
                    "bilateral_timeline": bilateral_timeline,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote summary JSON to {args.output_json}")


if __name__ == "__main__":
    main()
