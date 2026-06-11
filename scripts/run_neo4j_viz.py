#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Render Neo4j graph outputs using neo4j-viz or Plotly fallback."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.query_layer import TemporalGraphQueries  # noqa: E402
from src.reporting.plotly_viz import plot_event_timeline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize Neo4j events in Jupyter or export HTML."
    )
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-12-31")
    parser.add_argument("--output-html", type=Path, default=PROJECT_ROOT / "data" / "exports" / "plots" / "events.html")
    args = parser.parse_args()

    queries = TemporalGraphQueries()
    events = queries.events_within_date_range(
        start_date=args.start_date,
        end_date=args.end_date,
    )

    try:
        import neo4j_viz  # type: ignore

        print("neo4j-viz is available. Use it inside Jupyter/Streamlit as needed.")
        print("Events loaded:", len(events))
        return
    except Exception:
        pass

    fig = plot_event_timeline(events)
    if fig is None:
        raise SystemExit("No events available for plotting.")

    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(args.output_html)
    print(f"Plotly output written to {args.output_html}")


if __name__ == "__main__":
    main()
