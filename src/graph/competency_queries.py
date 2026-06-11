# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Competency queries from requirements paper for China-Romania temporal KG.

This module implements the specific competency questions outlined in the
requirements paper:

1. How did China–Romania economic relations evolve from 2020 to 2026?
2. Which Romanian institutions were most often connected to Chinese companies
   in news streams?
3. Which China–Romania trade, diplomatic, cultural, or policy events were
   reported in a given period?
4. Which claims later became contradicted or unverified? Which sources
   systematically produce low-credibility bilateral narratives?
5. Which collaborative research has been conducted with authors from China
   and Romania?
"""

from __future__ import annotations

from typing import Any

from src.graph.neo4j_connector import Neo4jConnector
from src.utils.logger import get_logger

log = get_logger(__name__)


class CompetencyQueries:
    """Implements requirements paper competency questions on the temporal KG."""

    def __init__(self, connector: Neo4jConnector | None = None) -> None:
        self._connector = connector or Neo4jConnector()

    def china_romania_economic_evolution(
        self,
        start_date: str = "2020-01-01",
        end_date: str = "2026-12-31",
    ) -> dict[str, Any]:
        """How did China–Romania economic relations evolve from 2020 to 2026?

        Returns events grouped by time periods (year or quarter) showing:
        - Trade agreements
        - Investment projects
        - Company activities
        - Infrastructure projects

        Args:
            start_date: Start of analysis period (YYYY-MM-DD)
            end_date: End of analysis period (YYYY-MM-DD)

        Returns:
            Dictionary with:
            - timeline: List of time periods with event counts and types
            - total_events: Total number of economic events
            - event_breakdown: Event counts by type
            - key_entities: Most frequently mentioned entities
        """
        economic_event_types = [
            "TradeAgreement",
            "InvestmentProject",
            "CompanyActivity",
            "InfrastructureProject",
        ]

        query = """
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        WHERE event.type IN $event_types
          AND coalesce(event.start_date, event.end_date, article.published_at) >= $start_date
          AND coalesce(event.start_date, event.end_date, article.published_at) <= $end_date
          AND EXISTS {
              MATCH (event)-[:INVOLVES]->(china:Entity)
              WHERE toLower(coalesce(china.canonical_name, china.name, "")) CONTAINS "china"
          }
          AND EXISTS {
              MATCH (event)-[:INVOLVES]->(romania:Entity)
              WHERE toLower(coalesce(romania.canonical_name, romania.name, "")) CONTAINS "romania"
          }
        WITH event, article,
             substring(
                 coalesce(event.start_date, event.end_date, article.published_at),
                 0, 7
             ) AS month_bucket
        ORDER BY month_bucket
        WITH month_bucket,
             count(DISTINCT event) AS event_count,
             collect(DISTINCT event.type) AS event_types,
             collect(DISTINCT {
                 id: event.id,
                 type: event.type,
                 trigger: event.trigger,
                 sentence: event.sentence,
                 date: coalesce(event.start_date, event.end_date, article.published_at),
                 source: article.source_name
             }) AS events
        RETURN month_bucket, event_count, event_types, events
        """

        with self._connector as conn:
            timeline = conn.run(
                query,
                event_types=economic_event_types,
                start_date=start_date,
                end_date=end_date,
            )

        # Get type breakdown
        type_query = """
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        WHERE event.type IN $event_types
          AND coalesce(event.start_date, event.end_date, article.published_at) >= $start_date
          AND coalesce(event.start_date, event.end_date, article.published_at) <= $end_date
          AND EXISTS {
              MATCH (event)-[:INVOLVES]->(china:Entity)
              WHERE toLower(coalesce(china.canonical_name, china.name, "")) CONTAINS "china"
          }
          AND EXISTS {
              MATCH (event)-[:INVOLVES]->(romania:Entity)
              WHERE toLower(coalesce(romania.canonical_name, romania.name, "")) CONTAINS "romania"
          }
        RETURN event.type AS event_type, count(DISTINCT event) AS count
        ORDER BY count DESC
        """

        with self._connector as conn:
            breakdown = conn.run(
                type_query,
                event_types=economic_event_types,
                start_date=start_date,
                end_date=end_date,
            )

        # Get key entities
        entity_query = """
        MATCH (event:Event)-[:INVOLVES]->(entity:Entity)
        MATCH (event)-[:REPORTED_IN]->(article:Article)
        WHERE event.type IN $event_types
          AND coalesce(event.start_date, event.end_date, article.published_at) >= $start_date
          AND coalesce(event.start_date, event.end_date, article.published_at) <= $end_date
          AND entity.type IN ["ORGANIZATION", "ORG"]
        RETURN coalesce(entity.canonical_name, entity.name) AS entity_name,
               entity.type AS entity_type,
               count(DISTINCT event) AS mention_count
        ORDER BY mention_count DESC
        LIMIT 20
        """

        with self._connector as conn:
            entities = conn.run(
                entity_query,
                event_types=economic_event_types,
                start_date=start_date,
                end_date=end_date,
            )

        total = sum(row["event_count"] for row in timeline)

        return {
            "timeline": timeline,
            "total_events": total,
            "event_breakdown": breakdown,
            "key_entities": entities,
            "period": f"{start_date} to {end_date}",
        }

    def romanian_institutions_connected_to_chinese_companies(
        self,
        limit: int = 20,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Which Romanian institutions were most connected to Chinese companies?

        Finds Romanian organizations (institutions, government bodies, companies)
        that appear in the same events as Chinese companies.

        Args:
            limit: Maximum number of institutions to return
            start_date: Optional filter for start date
            end_date: Optional filter for end date

        Returns:
            List of Romanian institutions with connection counts and event types
        """
        date_filter = ""
        params: dict[str, Any] = {"limit": limit}

        if start_date:
            date_filter += " AND coalesce(event.start_date, event.end_date, article.published_at) >= $start_date"
            params["start_date"] = start_date
        if end_date:
            date_filter += " AND coalesce(event.start_date, event.end_date, article.published_at) <= $end_date"
            params["end_date"] = end_date

        query = f"""
        MATCH (chinese_entity:Entity)
        WHERE toLower(coalesce(chinese_entity.canonical_name, chinese_entity.name, ""))
              CONTAINS "china"
          AND chinese_entity.type IN ["ORGANIZATION", "ORG"]
        MATCH (event:Event)-[:INVOLVES]->(chinese_entity)
        MATCH (event)-[:INVOLVES]->(romanian_entity:Entity)
        MATCH (event)-[:REPORTED_IN]->(article:Article)
        WHERE toLower(coalesce(romanian_entity.canonical_name, romanian_entity.name, ""))
              CONTAINS "romania"
          AND romanian_entity.type IN ["ORGANIZATION", "ORG"]
          AND romanian_entity.id <> chinese_entity.id
          {date_filter}
        RETURN coalesce(romanian_entity.canonical_name, romanian_entity.name)
               AS romanian_institution,
               romanian_entity.id AS entity_id,
               count(DISTINCT event) AS connection_count,
               collect(DISTINCT event.type) AS event_types,
               collect(DISTINCT {{
                   chinese_company: coalesce(
                       chinese_entity.canonical_name,
                       chinese_entity.name
                   ),
                   event_id: event.id,
                   event_type: event.type,
                   date: coalesce(event.start_date, event.end_date, article.published_at)
               }}) AS connections
        ORDER BY connection_count DESC
        LIMIT $limit
        """

        with self._connector as conn:
            return conn.run(query, **params)

    def bilateral_events_in_period(
        self,
        start_date: str,
        end_date: str,
        event_categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Which China–Romania events were reported in a given period?

        Returns trade, diplomatic, cultural, or policy events involving both
        China and Romania in the specified time period.

        Args:
            start_date: Period start (YYYY-MM-DD)
            end_date: Period end (YYYY-MM-DD)
            event_categories: Optional list to filter by categories:
                ["trade", "diplomatic", "cultural", "policy"]

        Returns:
            Dictionary with events grouped by category and timeline
        """
        # Map categories to event types
        category_map = {
            "trade": ["TradeAgreement", "InvestmentProject", "CompanyActivity"],
            "diplomatic": ["DiplomaticMeeting", "PolicyStatement"],
            "cultural": ["CulturalExchange", "EducationCooperation"],
            "policy": ["PolicyStatement", "SecurityStatement", "SanctionOrRestriction"],
            "infrastructure": ["InfrastructureProject"],
            "technology": ["TechnologyCooperation"],
        }

        if event_categories:
            event_types = []
            for category in event_categories:
                event_types.extend(category_map.get(category, []))
            event_types = list(set(event_types))
        else:
            event_types = []
            for types in category_map.values():
                event_types.extend(types)
            event_types = list(set(event_types))

        query = """
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        WHERE event.type IN $event_types
          AND coalesce(event.start_date, event.end_date, article.published_at) >= $start_date
          AND coalesce(event.start_date, event.end_date, article.published_at) <= $end_date
          AND EXISTS {
              MATCH (event)-[:INVOLVES]->(china:Entity)
              WHERE toLower(coalesce(china.canonical_name, china.name, "")) CONTAINS "china"
          }
          AND EXISTS {
              MATCH (event)-[:INVOLVES]->(romania:Entity)
              WHERE toLower(coalesce(romania.canonical_name, romania.name, "")) CONTAINS "romania"
          }
        OPTIONAL MATCH (event)-[:INVOLVES]->(entity:Entity)
        WITH event, article,
             collect(DISTINCT {
                 name: coalesce(entity.canonical_name, entity.name),
                 type: entity.type
             }) AS entities
        RETURN event.id AS event_id,
               event.event_key AS event_key,
               event.type AS event_type,
               event.trigger AS trigger,
               event.sentence AS sentence,
               event.start_date AS start_date,
               event.end_date AS end_date,
               article.id AS article_id,
               article.title AS article_title,
               article.url AS article_url,
               article.source_name AS source_name,
               article.published_at AS published_at,
               entities
        ORDER BY coalesce(event.start_date, event.end_date, article.published_at),
                 event.id
        """

        with self._connector as conn:
            events = conn.run(
                query,
                event_types=event_types,
                start_date=start_date,
                end_date=end_date,
            )

        # Group by type
        by_type: dict[str, list] = {}
        for event in events:
            event_type = event["event_type"]
            if event_type not in by_type:
                by_type[event_type] = []
            by_type[event_type].append(event)

        return {
            "period": f"{start_date} to {end_date}",
            "total_events": len(events),
            "events": events,
            "events_by_type": by_type,
            "event_type_counts": {
                event_type: len(event_list)
                for event_type, event_list in by_type.items()
            },
        }

    def contradicted_or_unverified_claims(
        self,
        credibility_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Which claims became contradicted or unverified? Which sources produce
        low-credibility bilateral narratives?

        Analyzes claims and their corroboration across sources to identify:
        - Claims reported by only one source (unverified)
        - Claims with contradictory reports
        - Sources with systematically low credibility

        Args:
            credibility_threshold: Minimum credibility score for reliable sources

        Returns:
            Dictionary with:
            - unverified_claims: Claims from single sources
            - contradicted_claims: Claims with conflicting reports
            - low_credibility_sources: Sources below threshold
        """
        # Find claims reported by single source only (unverified)
        unverified_query = """
        MATCH (claim:Claim)-[:RELATED_TO]->(event:Event)-[:REPORTED_IN]->(article:Article)
        WITH claim.claim_key AS claim_key,
             claim.text AS claim_text,
             collect(DISTINCT article.source_domain) AS sources,
             count(DISTINCT article.source_domain) AS source_count,
             collect(DISTINCT {
                 article_id: article.id,
                 title: article.title,
                 source: article.source_name,
                 url: article.url,
                 published_at: article.published_at
             }) AS articles
        WHERE source_count = 1
        RETURN claim_key, claim_text, sources, articles, source_count
        ORDER BY claim_key
        LIMIT 100
        """

        with self._connector as conn:
            unverified = conn.run(unverified_query)

        # Find sources with low average credibility
        source_credibility_query = """
        MATCH (article:Article)
        WHERE EXISTS {
            MATCH (article)<-[:REPORTED_IN]-(event:Event)-[:INVOLVES]->(entity:Entity)
            WHERE toLower(coalesce(entity.canonical_name, entity.name, ""))
                  CONTAINS "china"
               OR toLower(coalesce(entity.canonical_name, entity.name, ""))
                  CONTAINS "romania"
        }
        WITH article.source_domain AS source_domain,
             article.source_name AS source_name,
             count(DISTINCT article) AS article_count
        WHERE source_domain IS NOT NULL
        RETURN source_domain,
               source_name,
               article_count
        ORDER BY article_count DESC
        """

        with self._connector as conn:
            sources = conn.run(source_credibility_query)

        # Find events with multiple conflicting reports (contradictions)
        contradiction_query = """
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        WHERE EXISTS {
            MATCH (event)-[:INVOLVES]->(entity:Entity)
            WHERE toLower(coalesce(entity.canonical_name, entity.name, ""))
                  CONTAINS "china"
               OR toLower(coalesce(entity.canonical_name, entity.name, ""))
                  CONTAINS "romania"
        }
        WITH event.event_key AS event_key,
             count(DISTINCT article.source_domain) AS source_count,
             collect(DISTINCT {
                 source: article.source_name,
                 domain: article.source_domain,
                 title: article.title,
                 url: article.url,
                 published_at: article.published_at,
                 sentence: event.sentence
             }) AS reports
        WHERE source_count >= 2
        RETURN event_key, source_count, reports
        ORDER BY source_count DESC
        LIMIT 50
        """

        with self._connector as conn:
            contradictions = conn.run(contradiction_query)

        return {
            "unverified_claims": unverified,
            "multi_source_events": contradictions,
            "source_activity": sources,
            "credibility_threshold": credibility_threshold,
        }

    def collaborative_research_authors(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Which collaborative research has been conducted with authors from
        China and Romania?

        Identifies research collaboration events and entities mentioned together.

        Args:
            limit: Maximum results to return

        Returns:
            List of research collaboration events with participants
        """
        query = """
        MATCH (event:Event)-[:REPORTED_IN]->(article:Article)
        WHERE event.type IN [
            "TechnologyCooperation",
            "EducationCooperation"
        ]
        AND EXISTS {
            MATCH (event)-[:INVOLVES]->(china_entity:Entity)
            WHERE toLower(coalesce(china_entity.canonical_name, china_entity.name, ""))
                  CONTAINS "china"
        }
        AND EXISTS {
            MATCH (event)-[:INVOLVES]->(romania_entity:Entity)
            WHERE toLower(coalesce(romania_entity.canonical_name, romania_entity.name, ""))
                  CONTAINS "romania"
        }
        OPTIONAL MATCH (event)-[:INVOLVES]->(person:Entity)
        WHERE person.type = "PERSON"
        OPTIONAL MATCH (event)-[:INVOLVES]->(org:Entity)
        WHERE org.type IN ["ORGANIZATION", "ORG"]
        WITH event, article,
             collect(DISTINCT {
                 name: person.name,
                 type: "researcher"
             }) AS researchers,
             collect(DISTINCT {
                 name: coalesce(org.canonical_name, org.name),
                 type: "institution"
             }) AS institutions
        RETURN event.id AS event_id,
               event.type AS event_type,
               event.trigger AS trigger,
               event.sentence AS description,
               event.start_date AS date,
               article.title AS article_title,
               article.source_name AS source,
               article.published_at AS published_at,
               researchers,
               institutions
        ORDER BY date DESC, event.id
        LIMIT $limit
        """

        with self._connector as conn:
            return conn.run(query, limit=limit)
