"""Reusable temporal query helpers for the Neo4j knowledge graph."""

from __future__ import annotations

import json
import calendar
from typing import Any

from src.graph.neo4j_connector import Neo4jConnector


class TemporalGraphQueries:
    """Notebook-friendly wrappers around the project Neo4j schema."""

    def __init__(self, connector: Neo4jConnector | None = None) -> None:
        self._connector = connector or Neo4jConnector()

    def events_within_date_range(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._event_filters(
            start_date=start_date,
            end_date=end_date,
            source=source,
            entity=entity,
            event_type=event_type,
        )
        query = f"""
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        OPTIONAL MATCH (event)-[:HAS_TIME]->(temporal:TemporalExpression)
        WHERE {where_clause}
        OPTIONAL MATCH (event)-[:INVOLVES]->(entity_node:Entity)
        WITH event, article, temporal,
             collect(
                 DISTINCT {{
                     id: entity_node.id,
                     name: entity_node.name,
                     canonical_name: entity_node.canonical_name,
                     type: entity_node.type
                 }}
             ) AS entities
        RETURN event.id AS event_id,
               event.event_key AS event_key,
               event.type AS event_type,
               event.trigger AS trigger,
               event.normalized_trigger AS normalized_trigger,
               event.sentence AS sentence,
               event.start_date AS start_date,
               event.end_date AS end_date,
               temporal.id AS temporal_id,
               temporal.kind AS temporal_kind,
               temporal.normalized_value AS temporal_value,
               article.id AS article_id,
               article.title AS article_title,
               article.url AS article_url,
               article.source_name AS source_name,
               article.source_domain AS source_domain,
               article.published_at AS published_at,
               entities AS entities
        ORDER BY
            coalesce(event.start_date, event.end_date, article.published_at),
            event.id
        """
        with self._connector as conn:
            rows = conn.run(query, **params)
        return [self._decode_event_row(row) for row in rows]

    def event_counts_by_year(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._event_filters(
            start_date=start_date,
            end_date=end_date,
            source=source,
            entity=entity,
            event_type=event_type,
        )
        query = f"""
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        OPTIONAL MATCH (event)-[:HAS_TIME]->(temporal:TemporalExpression)
        WHERE {where_clause}
        WITH substring(
                 coalesce(
                     event.start_date,
                     event.end_date,
                     article.published_at
                 ),
                 0,
                 4
             ) AS year,
             count(DISTINCT event) AS event_count
        WHERE year IS NOT NULL AND year <> ""
        RETURN year, event_count
        ORDER BY year
        """
        with self._connector as conn:
            return conn.run(query, **params)

    def event_counts_by_type(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        entity: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._event_filters(
            start_date=start_date,
            end_date=end_date,
            source=source,
            entity=entity,
        )
        query = f"""
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        OPTIONAL MATCH (event)-[:HAS_TIME]->(temporal:TemporalExpression)
        WHERE {where_clause}
        RETURN event.type AS event_type,
               count(DISTINCT event) AS event_count
        ORDER BY event_count DESC, event_type
        """
        with self._connector as conn:
            return conn.run(query, **params)

    def organizations_connected_to(
        self,
        focus_entity: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        event_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._event_filters(
            start_date=start_date,
            end_date=end_date,
            source=source,
            event_type=event_type,
        )
        params["focus_entity"] = focus_entity.lower()
        params["limit"] = limit
        query = f"""
        MATCH (focus:Entity)
        WHERE toLower(coalesce(focus.canonical_name, focus.name, "")) CONTAINS
              $focus_entity
        MATCH (event:Event)-[:INVOLVES]->(focus)
        MATCH (event)-[:INVOLVES]->(org:Entity)
        MATCH (event)-[:REPORTED_IN]->(article:Article)
        OPTIONAL MATCH (event)-[:HAS_TIME]->(temporal:TemporalExpression)
        WHERE org.id <> focus.id
          AND org.type IN ["ORGANIZATION", "ORG"]
          AND {where_clause}
        RETURN coalesce(org.canonical_name, org.name) AS organization,
               org.id AS entity_id,
               count(DISTINCT event) AS connection_count,
               collect(DISTINCT event.type) AS event_types
        ORDER BY connection_count DESC, organization
        LIMIT $limit
        """
        with self._connector as conn:
            return conn.run(query, **params)

    def bilateral_activity_timeline(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._event_filters(
            start_date=start_date,
            end_date=end_date,
            source=source,
            event_type=event_type,
        )
        query = f"""
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        OPTIONAL MATCH (event)-[:HAS_TIME]->(temporal:TemporalExpression)
        WHERE {where_clause}
          AND EXISTS {{
              MATCH (event)-[:INVOLVES]->(china:Entity)
              WHERE toLower(
                        coalesce(china.canonical_name, china.name, "")
                    ) CONTAINS "china"
          }}
          AND EXISTS {{
              MATCH (event)-[:INVOLVES]->(romania:Entity)
              WHERE toLower(
                        coalesce(romania.canonical_name, romania.name, "")
                    ) CONTAINS "romania"
          }}
        WITH substring(
                 coalesce(
                     event.start_date,
                     event.end_date,
                     article.published_at
                 ),
                 0,
                 7
             ) AS month_bucket,
             count(DISTINCT event) AS event_count,
             collect(DISTINCT event.type) AS event_types
        WHERE month_bucket IS NOT NULL AND month_bucket <> ""
        RETURN month_bucket, event_count, event_types
        ORDER BY month_bucket
        """
        with self._connector as conn:
            return conn.run(query, **params)

    def articles_supporting_event(self, event_id: str) -> list[dict[str, Any]]:
        query = """
        MATCH (seed:Event {id: $event_id})
        MATCH (event:Event {event_key: seed.event_key})
              -[:REPORTED_IN]->(article:Article)
        OPTIONAL MATCH (claim:Claim)-[:RELATED_TO]->(event)
        RETURN DISTINCT article.id AS article_id,
               article.title AS title,
               article.url AS url,
               article.source_name AS source_name,
               article.source_domain AS source_domain,
               article.published_at AS published_at,
               event.id AS supporting_event_id,
               event.type AS event_type,
               claim.id AS claim_id,
               claim.text AS claim_text
        ORDER BY article.published_at, article.id
        """
        with self._connector as conn:
            return conn.run(query, event_id=event_id)

    def events_linked_to_source(
        self,
        source: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.events_within_date_range(
            start_date=start_date,
            end_date=end_date,
            source=source,
            entity=entity,
            event_type=event_type,
        )

    def _event_filters(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        entity: str | None = None,
        event_type: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        clauses = ["1 = 1"]
        params: dict[str, Any] = {}
        if start_date:
            params["start_date"] = self._normalize_date(start_date, end=False)
            clauses.append(
                "coalesce("
                "event.end_date, event.start_date, article.published_at"
                ") >= $start_date"
            )
        if end_date:
            params["end_date"] = self._normalize_date(end_date, end=True)
            clauses.append(
                "coalesce("
                "event.start_date, event.end_date, article.published_at"
                ") <= $end_date"
            )
        if source:
            params["source"] = source.lower()
            clauses.append(
                "("
                "toLower(coalesce(article.source_name, '')) "
                "CONTAINS $source OR "
                "toLower(coalesce(article.source_domain, '')) "
                "CONTAINS $source OR "
                "toLower(coalesce(article.url, '')) CONTAINS $source"
                ")"
            )
        if entity:
            params["entity"] = entity.lower()
            clauses.append(
                "EXISTS { "
                "MATCH (event)-[:INVOLVES]->(filter_entity:Entity) "
                "WHERE toLower("
                "coalesce("
                "filter_entity.canonical_name, filter_entity.name, ''"
                ")"
                ") CONTAINS $entity "
                "}"
            )
        if event_type:
            params["event_type"] = event_type.lower()
            clauses.append("toLower(coalesce(event.type, '')) = $event_type")
        return " AND ".join(clauses), params

    @staticmethod
    def _normalize_date(raw_value: str, *, end: bool) -> str:
        text = str(raw_value).strip()
        if len(text) == 10:
            return text
        if len(text) == 7:
            year, month = (int(part) for part in text.split("-"))
            if not end:
                return f"{year:04d}-{month:02d}-01"
            last_day = calendar.monthrange(year, month)[1]
            return f"{year:04d}-{month:02d}-{last_day:02d}"
        if len(text) == 4:
            return f"{text}-12-31" if end else f"{text}-01-01"
        return text[:10]

    @staticmethod
    def _decode_event_row(row: dict[str, Any]) -> dict[str, Any]:
        temporal_value = row.get("temporal_value")
        if isinstance(temporal_value, str):
            try:
                row["temporal_value"] = json.loads(temporal_value)
            except json.JSONDecodeError:
                row["temporal_value"] = temporal_value
        row["entities"] = [
            entity
            for entity in row.get("entities", [])
            if (
                entity.get("id")
                or entity.get("canonical_name")
                or entity.get("name")
            )
        ]
        return row
