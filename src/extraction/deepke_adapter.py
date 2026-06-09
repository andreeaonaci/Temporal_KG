"""Normalize DeepKE outputs to the project extraction schema."""

from __future__ import annotations

from typing import Any

from src.extraction.pipeline_utils import stable_id


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_entities(
    payload: dict[str, Any],
    *,
    article_id: str,
    sentence_lookup: dict[int, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (entities, mentions) from a DeepKE payload."""
    entities: list[dict[str, Any]] = []
    mentions: list[dict[str, Any]] = []

    raw_entities = payload.get("entities") or payload.get("entity_list") or []
    for item in raw_entities:
        text = _safe_text(item.get("text") or item.get("name"))
        label = _safe_text(item.get("type") or item.get("label"))
        start = int(item.get("start", 0))
        end = int(item.get("end", start + len(text)))
        sentence_index = int(item.get("sentence_index", 0))
        sentence = ""
        if sentence_lookup and sentence_index in sentence_lookup:
            sentence = sentence_lookup[sentence_index].get("sentence", "")

        entity_id = item.get("entity_id") or stable_id(article_id, text, label)
        mention_id = stable_id(article_id, text, start, end, label)

        mentions.append(
            {
                "mention_id": mention_id,
                "entity_id": entity_id,
                "article_id": article_id,
                "text": text,
                "normalized_name": text,
                "entity_type": label or "ENTITY",
                "sentence": sentence,
                "sentence_index": sentence_index,
                "start_char": start,
                "end_char": end,
                "confidence": float(item.get("confidence", 0.7)),
            }
        )
        entities.append(
            {
                "entity_id": entity_id,
                "canonical_name": text,
                "entity_type": label or "ENTITY",
                "aliases": [text],
                "article_ids": [article_id],
                "mention_ids": [mention_id],
                "mention_count": 1,
                "confidence": float(item.get("confidence", 0.7)),
            }
        )

    return entities, mentions


def normalize_relations(
    payload: dict[str, Any],
    *,
    article_id: str,
) -> list[dict[str, Any]]:
    """Return relation rows from a DeepKE payload."""
    relations: list[dict[str, Any]] = []
    raw_relations = payload.get("relations") or payload.get("relation_list") or []
    for item in raw_relations:
        source_id = item.get("head_id") or item.get("source_id")
        target_id = item.get("tail_id") or item.get("target_id")
        if not source_id or not target_id:
            continue
        relation_type = _safe_text(item.get("relation") or item.get("type"))
        sentence = _safe_text(item.get("sentence"))
        sentence_index = int(item.get("sentence_index", 0))
        relation_id = stable_id(
            article_id, relation_type, source_id, target_id, sentence_index
        )
        relations.append(
            {
                "relation_id": relation_id,
                "article_id": article_id,
                "relation_type": relation_type or "related_to",
                "source_id": source_id,
                "source_type": item.get("source_type", "entity"),
                "target_id": target_id,
                "target_type": item.get("target_type", "entity"),
                "sentence": sentence,
                "sentence_index": sentence_index,
                "event_id": item.get("event_id"),
                "temporal_id": item.get("temporal_id"),
                "confidence": float(item.get("confidence", 0.7)),
            }
        )

    return relations
