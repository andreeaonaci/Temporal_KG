#!/usr/bin/env python3
"""Check Neo4j database contents and connection."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.neo4j_connector import Neo4jConnector
from src.utils.logger import get_logger

log = get_logger(__name__)


def main() -> None:
    """Check Neo4j stats."""
    try:
        with Neo4jConnector() as conn:
            log.info("Connected to Neo4j")
            
            # Count nodes by label
            query_labels = """
            MATCH (n)
            RETURN labels(n)[0] as label, count(n) as count
            ORDER BY count DESC
            """
            labels = conn.run(query_labels)
            log.info("Node counts by label:")
            for row in labels:
                log.info("  %s: %d", row.get('label'), row.get('count', 0))
            
            # Count total nodes
            total_nodes = conn.run("MATCH (n) RETURN count(n) as count")[0]
            log.info("Total nodes: %d", total_nodes.get('count', 0))
            
            # Count relationships
            total_rels = conn.run("MATCH ()-[r]->() RETURN count(r) as count")[0]
            log.info("Total relationships: %d", total_rels.get('count', 0))
            
            # Show sample nodes
            sample = conn.run("MATCH (n) RETURN n LIMIT 5")
            if sample:
                log.info("Sample nodes (first 5):")
                for i, row in enumerate(sample, 1):
                    log.info("  %d. %s", i, row)
            else:
                log.warning("No nodes found in database!")
                
    except Exception as exc:
        log.error("Error checking Neo4j: %s", exc)
        raise


if __name__ == "__main__":
    main()
