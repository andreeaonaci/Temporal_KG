#!/usr/bin/env python3
"""Initialize Neo4j constraints and indexes for the extracted graph."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.graph_loader import GraphSchemaInitializer

if __name__ == "__main__":
    GraphSchemaInitializer().initialize()
    print("Neo4j schema initialized.")
