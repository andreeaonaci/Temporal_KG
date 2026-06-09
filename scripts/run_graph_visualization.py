#!/usr/bin/env python3
"""Build a lightweight event-entity graph and persist it from CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.query_layer import TemporalGraphQueries  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a NetworkX graph from Neo4j event-query results."
    )
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-12-31")
    parser.add_argument("--max-events", type=int, default=20)
    parser.add_argument(
        "--output-graphml",
        type=Path,
        default=PROJECT_ROOT / "data" / "exports" / "graph" / "event_entity.graphml",
    )
    args = parser.parse_args()

    queries = TemporalGraphQueries()
    events = queries.events_within_date_range(
        start_date=args.start_date,
        end_date=args.end_date,
    )[: max(args.max_events, 0)]

    graph = nx.Graph()
    for event in events:
        event_id = event.get("event_id")
        if not event_id:
            continue
        graph.add_node(event_id, label=event.get("event_type") or "event", kind="event")
        for entity in event.get("entities", []):
            entity_id = entity.get("id")
            if not entity_id:
                continue
            graph.add_node(
                entity_id,
                label=entity.get("canonical_name") or entity.get("name") or "entity",
                kind="entity",
            )
            graph.add_edge(event_id, entity_id)

    args.output_graphml.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, args.output_graphml)
    print(f"Graph nodes: {graph.number_of_nodes()}")
    print(f"Graph edges: {graph.number_of_edges()}")
    print(f"Wrote graph to {args.output_graphml}")


if __name__ == "__main__":
    main()
