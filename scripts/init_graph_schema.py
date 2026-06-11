#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

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
