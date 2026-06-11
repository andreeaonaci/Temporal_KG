# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.graph.neo4j_connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Thin wrapper around the official Neo4j Python driver.
Not used until the graph-build phase — import is guarded so the project
runs fine without Neo4j installed.

Usage
-----
    from src.graph.neo4j_connector import Neo4jConnector

    with Neo4jConnector() as conn:
        conn.run("MERGE (n:Entity {name: $name})", name="China")
"""

from __future__ import annotations

from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class Neo4jConnector:
    """Manages a single Neo4j driver session."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._uri = uri or settings("database.neo4j_uri", "bolt://localhost:7687")
        self._user = user or settings("database.neo4j_user", "neo4j")
        self._password = password or settings("database.neo4j_password", "")
        self._driver: Any = None

    def connect(self) -> "Neo4jConnector":
        try:
            from neo4j import GraphDatabase  # lazy import
            self._driver = GraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            )
            self._driver.verify_connectivity()
            log.info("Connected to Neo4j at %s", self._uri)
        except ImportError:
            log.error("neo4j package not installed. Run: pip install neo4j")
            raise
        except Exception as exc:
            log.error("Failed to connect to Neo4j: %s", exc)
            raise
        return self

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None
            log.info("Neo4j connection closed.")

    def run(self, query: str, **params: Any) -> list[dict]:
        """Execute a Cypher query and return all records as dicts."""
        if not self._driver:
            raise RuntimeError("Not connected. Call connect() first.")
        with self._driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def __enter__(self) -> "Neo4jConnector":
        return self.connect()

    def __exit__(self, *_: Any) -> None:
        self.close()
