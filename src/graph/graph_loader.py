"""Neo4j graph schema initialization and JSON loading."""

from __future__ import annotations

import calendar
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.extraction.pipeline_utils import (
    build_claim_signature,
    build_event_signature,
    load_json_by_article,
    stable_json,
    stable_id,
)
from src.graph.cypher import (
    ARTICLE_BATCH_QUERY,
    CLAIM_BATCH_QUERY,
    ENTITY_BATCH_QUERY,
    EVENT_BATCH_QUERY,
    EVENT_ENTITY_BATCH_QUERY,
    EVENT_TIME_BATCH_QUERY,
    RELATED_BATCH_QUERY,
    SCHEMA_STATEMENTS,
    TEMPORAL_BATCH_QUERY,
)
from src.graph.neo4j_connector import Neo4jConnector


class GraphSchemaInitializer:
    """Create graph constraints and indexes."""

    def __init__(self, connector: Neo4jConnector | None = None) -> None:
        self._connector = connector or Neo4jConnector()

    def initialize(self) -> None:
        with self._connector as conn:
            for statement in SCHEMA_STATEMENTS:
                conn.run(statement)


class KnowledgeGraphLoader:
    """Load extracted JSON artifacts into Neo4j idempotently."""

    def __init__(self, connector: Neo4jConnector | None = None) -> None:
        self._connector = connector or Neo4jConnector()

    def load(
        self,
        entities_dir: Path,
        temporal_dir: Path,
        events_dir: Path,
        relations_dir: Path,
    ) -> None:
        entity_payloads = load_json_by_article(entities_dir)
        temporal_payloads = load_json_by_article(temporal_dir)
        event_payloads = load_json_by_article(events_dir)
        relation_payloads = load_json_by_article(relations_dir)

        article_ids = sorted(
            set(entity_payloads)
            | set(temporal_payloads)
            | set(event_payloads)
            | set(relation_payloads)
        )

        # Collect all records before touching Neo4j
        articles: list[dict] = []
        entity_rows: list[dict] = []
        temporal_rows: list[dict] = []
        event_rows: list[dict] = []
        claim_rows: list[dict] = []
        event_entity_rows: list[dict] = []
        event_time_rows: list[dict] = []
        relation_rows: list[dict] = []

        for article_id in article_ids:
            entity_payload = entity_payloads.get(article_id, {})
            temporal_payload = temporal_payloads.get(article_id, {})
            event_payload = event_payloads.get(article_id, {})
            relation_payload = relation_payloads.get(article_id, {})

            article = self._build_article_record(
                article_id,
                entity_payload.get("source_article")
                or temporal_payload.get("source_article")
                or event_payload.get("source_article")
                or relation_payload.get("source_article")
                or {},
            )
            articles.append(article)

            for mention in entity_payload.get("mentions", []):
                entity = self._entity_record(
                    mention, entity_payload.get("entities", [])
                )
                entity_rows.append(
                    {"entity": entity, "article_id": article_id, "mention": mention}
                )

            temporal_map: dict[str, dict] = {}
            for temporal in temporal_payload.get("temporal_expressions", []):
                temporal_record = self._temporal_record(temporal, article_id)
                temporal_map[temporal["temporal_id"]] = temporal_record
                temporal_rows.append(
                    {"temporal": temporal_record, "article_id": article_id}
                )

            for event in event_payload.get("events", []):
                temporal_record = temporal_map.get(event.get("temporal_id"))
                event_record = {
                    "id": event["event_id"],
                    "type": event["event_type"],
                    "trigger": event["trigger"],
                    "normalized_trigger": event["normalized_trigger"],
                    "sentence": event["sentence"],
                    "sentence_index": event.get("sentence_index", -1),
                    "confidence": event["confidence"],
                    "article_id": article_id,
                    "event_key": build_event_signature(
                        event,
                        temporal_record,
                        start_date=(
                            temporal_record.get("start_date")
                            if temporal_record
                            else None
                        ),
                        end_date=(
                            temporal_record.get("end_date")
                            if temporal_record
                            else None
                        ),
                    ),
                    "start_date": (
                        temporal_record.get("start_date")
                        if temporal_record
                        else self._article_date(article.get("published_at"))
                    ),
                    "end_date": (
                        temporal_record.get("end_date")
                        if temporal_record
                        else self._article_date(article.get("published_at"))
                    ),
                }
                event_rows.append(
                    {"event": event_record, "article_id": article_id}
                )
                for entity_id in event.get("participant_entity_ids", []):
                    event_entity_rows.append(
                        {
                            "event_id": event["event_id"],
                            "entity_id": entity_id,
                            "role": "participant",
                        }
                    )
                if event.get("temporal_id"):
                    event_time_rows.append(
                        {
                            "event_id": event["event_id"],
                            "temporal_id": event["temporal_id"],
                        }
                    )
                claim = self._claim_record(
                    article_id=article_id,
                    event=event,
                    event_record=event_record,
                )
                claim_rows.append(
                    {
                        "claim": claim,
                        "article_id": article_id,
                        "event_id": event["event_id"],
                    }
                )

            for relation in relation_payload.get("relations", []):
                relation_rows.append(
                    {
                        "source_id": relation["source_id"],
                        "target_id": relation["target_id"],
                        "relation": relation,
                    }
                )

        # Send everything to Neo4j in large batches
        batch = 500
        with self._connector as conn:
            for i in range(0, len(articles), batch):
                conn.run(ARTICLE_BATCH_QUERY, rows=articles[i:i + batch])
            for i in range(0, len(entity_rows), batch):
                conn.run(ENTITY_BATCH_QUERY, rows=entity_rows[i:i + batch])
            for i in range(0, len(temporal_rows), batch):
                conn.run(TEMPORAL_BATCH_QUERY, rows=temporal_rows[i:i + batch])
            for i in range(0, len(event_rows), batch):
                conn.run(EVENT_BATCH_QUERY, rows=event_rows[i:i + batch])
            for i in range(0, len(claim_rows), batch):
                conn.run(CLAIM_BATCH_QUERY, rows=claim_rows[i:i + batch])
            for i in range(0, len(event_entity_rows), batch):
                conn.run(EVENT_ENTITY_BATCH_QUERY, rows=event_entity_rows[i:i + batch])
            for i in range(0, len(event_time_rows), batch):
                conn.run(EVENT_TIME_BATCH_QUERY, rows=event_time_rows[i:i + batch])
            for i in range(0, len(relation_rows), batch):
                conn.run(RELATED_BATCH_QUERY, rows=relation_rows[i:i + batch])

    @staticmethod
    def _build_article_record(
        article_id: str, source_article: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": article_id,
            "article_id": article_id,
            "url": source_article.get("url"),
            "title": source_article.get("title"),
            "published_at": source_article.get("published_at"),
            "language": source_article.get("language"),
            "source_name": source_article.get("source_name"),
            "source_domain": KnowledgeGraphLoader._source_domain(
                source_article.get("url")
            ),
        }

    @staticmethod
    def _entity_record(
        mention: dict[str, Any], entities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        entity_map = {entity["entity_id"]: entity for entity in entities}
        entity = entity_map.get(mention["entity_id"], {})
        return {
            "id": mention["entity_id"],
            "name": mention["normalized_name"],
            "canonical_name": entity.get(
                "canonical_name",
                mention["normalized_name"],
            ),
            "type": mention["entity_type"],
            "aliases": entity.get("aliases", [mention["text"]]),
        }

    @staticmethod
    def _source_domain(url: str | None) -> str | None:
        if not url:
            return None
        return urlparse(url).netloc.lower().lstrip("www.")

    @staticmethod
    def _article_date(raw_value: str | None) -> str | None:
        if not raw_value:
            return None
        text = str(raw_value)
        if len(text) >= 10:
            return text[:10]
        return None

    @classmethod
    def _temporal_record(
        cls, temporal: dict[str, Any], article_id: str
    ) -> dict[str, Any]:
        normalized = temporal.get("normalized")
        start_date, end_date = cls._time_bounds(
            normalized,
            temporal.get("granularity"),
        )
        return {
            "id": temporal["temporal_id"],
            "article_id": article_id,
            "text": temporal["text"],
            "kind": temporal["kind"],
            "normalized_value": (
                stable_json(normalized)
                if isinstance(normalized, (dict, list))
                else normalized
            ),
            "granularity": temporal["granularity"],
            "resolved": temporal["resolved"],
            "ambiguous": temporal["ambiguous"],
            "confidence": temporal["confidence"],
            "reason": temporal.get("reason"),
            "anchor_date": temporal.get("anchor_date"),
            "start_date": start_date,
            "end_date": end_date,
            "sort_date": start_date or end_date or temporal.get("anchor_date"),
        }

    @staticmethod
    def _claim_record(
        *,
        article_id: str,
        event: dict[str, Any],
        event_record: dict[str, Any],
    ) -> dict[str, Any]:
        claim_signature = build_claim_signature(
            event.get("sentence", ""),
            event_type=event.get("event_type"),
            event_signature=event_record.get("event_key"),
        )
        return {
            "id": stable_id(article_id, event["event_id"], "claim"),
            "claim_key": claim_signature,
            "event_key": event_record.get("event_key"),
            "article_id": article_id,
            "event_id": event["event_id"],
            "event_type": event.get("event_type"),
            "text": event.get("sentence"),
            "normalized_trigger": event.get("normalized_trigger"),
            "participant_entity_ids": sorted(
                event.get("participant_entity_ids", [])
            ),
            "temporal_id": event.get("temporal_id"),
        }

    @classmethod
    def _time_bounds(
        cls,
        normalized: Any,
        granularity: str | None,
    ) -> tuple[str | None, str | None]:
        if normalized is None:
            return None, None
        if isinstance(normalized, dict):
            return (
                cls._expand_date(normalized.get("start")),
                cls._expand_date(normalized.get("end"), is_end=True),
            )
        if isinstance(normalized, str) and normalized.startswith("P"):
            return None, None
        value = str(normalized)
        return (
            cls._expand_date(value, granularity=granularity),
            cls._expand_date(value, is_end=True, granularity=granularity),
        )

    @staticmethod
    def _expand_date(
        value: str | None,
        *,
        is_end: bool = False,
        granularity: str | None = None,
    ) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        if len(text) >= 10:
            try:
                return datetime.fromisoformat(text[:10]).date().isoformat()
            except ValueError:
                return text[:10]
        if len(text) == 7:
            try:
                year, month = text.split("-")
                year_int = int(year)
                month_int = int(month)
                day = (
                    calendar.monthrange(year_int, month_int)[1]
                    if is_end
                    else 1
                )
                return f"{year}-{month}-{day:02d}"
            except ValueError:
                # Handle invalid year/month placeholders like 'XXXX'
                return None
        if len(text) == 4:
            try:
                int(text)  # Validate year is numeric
                return f"{text}-12-31" if is_end else f"{text}-01-01"
            except ValueError:
                # Handle invalid year placeholders like 'XXXX'
                return None
        if granularity == "month" and len(text) > 7:
            return text[:7] + ("-31" if is_end else "-01")
        return None
