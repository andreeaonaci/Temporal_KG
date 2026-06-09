#!/usr/bin/env python3
"""Run a few reusable Neo4j query examples."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.query_layer import TemporalGraphQueries  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run reusable Neo4j query examples."
    )
    parser.parse_args()

    queries = TemporalGraphQueries()
    examples = {
        "recent_events": queries.events_within_date_range(
            start_date="2025-01-01",
            end_date="2026-12-31",
        ),
        "event_counts_by_year": queries.event_counts_by_year(),
        "event_counts_by_type": queries.event_counts_by_type(),
        "china_org_connections": queries.organizations_connected_to("China"),
        "bilateral_timeline": queries.bilateral_activity_timeline(),
    }
    print(json.dumps(examples, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
