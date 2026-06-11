# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Cypher builders for loading extracted JSON into Neo4j."""

from __future__ import annotations

SCHEMA_STATEMENTS = [
    (
        "CREATE CONSTRAINT article_id_unique IF NOT EXISTS "
        "FOR (n:Article) REQUIRE n.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
        "FOR (n:Entity) REQUIRE n.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT event_id_unique IF NOT EXISTS "
        "FOR (n:Event) REQUIRE n.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT temporal_id_unique IF NOT EXISTS "
        "FOR (n:TemporalExpression) REQUIRE n.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS "
        "FOR (n:Claim) REQUIRE n.id IS UNIQUE"
    ),
    (
        "CREATE INDEX article_published_idx IF NOT EXISTS "
        "FOR (n:Article) ON (n.published_at)"
    ),
    (
        "CREATE INDEX article_source_idx IF NOT EXISTS "
        "FOR (n:Article) ON (n.source_domain)"
    ),
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (n:Entity) ON (n.type)",
    "CREATE INDEX event_type_idx IF NOT EXISTS FOR (n:Event) ON (n.type)",
    "CREATE INDEX event_key_idx IF NOT EXISTS FOR (n:Event) ON (n.event_key)",
    (
        "CREATE INDEX temporal_range_idx IF NOT EXISTS "
        "FOR (n:TemporalExpression) ON (n.start_date, n.end_date)"
    ),
]

ARTICLE_BATCH_QUERY = """
UNWIND $rows AS article
MERGE (a:Article {id: article.id})
SET a += article
"""

ENTITY_BATCH_QUERY = """
UNWIND $rows AS row
MERGE (e:Entity {id: row.entity.id})
SET e += row.entity
WITH e, row
MATCH (a:Article {id: row.article_id})
MERGE (a)-[rel:MENTIONS {mention_id: row.mention.mention_id}]->(e)
SET rel += row.mention
MERGE (e)-[:REPORTED_IN]->(a)
"""

TEMPORAL_BATCH_QUERY = """
UNWIND $rows AS row
MERGE (t:TemporalExpression {id: row.temporal.id})
SET t += row.temporal
WITH t, row
MATCH (a:Article {id: row.article_id})
MERGE (t)-[:REPORTED_IN]->(a)
"""

EVENT_BATCH_QUERY = """
UNWIND $rows AS row
MERGE (ev:Event {id: row.event.id})
SET ev += row.event
WITH ev, row
MATCH (a:Article {id: row.article_id})
MERGE (ev)-[:REPORTED_IN]->(a)
"""

CLAIM_BATCH_QUERY = """
UNWIND $rows AS row
MERGE (c:Claim {id: row.claim.id})
SET c += row.claim
WITH c, row
MATCH (a:Article {id: row.article_id})
MATCH (ev:Event {id: row.event_id})
MERGE (c)-[:REPORTED_IN]->(a)
MERGE (c)-[:RELATED_TO]->(ev)
"""

EVENT_ENTITY_BATCH_QUERY = """
UNWIND $rows AS row
MATCH (ev:Event {id: row.event_id})
MATCH (e:Entity {id: row.entity_id})
MERGE (ev)-[rel:INVOLVES]->(e)
SET rel.role = COALESCE(row.role, 'participant')
"""

EVENT_TIME_BATCH_QUERY = """
UNWIND $rows AS row
MATCH (ev:Event {id: row.event_id})
MATCH (t:TemporalExpression {id: row.temporal_id})
MERGE (ev)-[:HAS_TIME]->(t)
"""

RELATED_BATCH_QUERY = """
UNWIND $rows AS row
MATCH (source {id: row.source_id})
MATCH (target {id: row.target_id})
MERGE (source)-[rel:RELATED_TO {relation_id: row.relation.relation_id}]->(target)
SET rel += row.relation
"""
