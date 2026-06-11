#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Load extracted entity, temporal, event, and relation JSON into Neo4j."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.graph_loader import KnowledgeGraphLoader
from src.utils.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load extracted JSON outputs into Neo4j."
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
        "--relations-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "relations",
    )
    args = parser.parse_args()

    KnowledgeGraphLoader().load(
        args.entities_dir, args.temporals_dir, args.events_dir, args.relations_dir
    )
    print("Neo4j load complete.")


if __name__ == "__main__":
    main()
