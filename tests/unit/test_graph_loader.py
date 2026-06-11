# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

import json

from src.graph.graph_loader import KnowledgeGraphLoader


class FakeConnector:
    def __init__(self) -> None:
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query: str, **params):
        self.calls.append((query, params))
        return []


def test_graph_loader_merges_article_entity_event_temporal_and_relation(
    tmp_path,
):
    article_id = "article-1"
    entities_dir = tmp_path / "entities"
    temporals_dir = tmp_path / "temporals"
    events_dir = tmp_path / "events"
    relations_dir = tmp_path / "relations"
    for directory in (entities_dir, temporals_dir, events_dir, relations_dir):
        directory.mkdir()

    (entities_dir / f"{article_id}.entities.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "source_article": {
                    "url": "https://example.com",
                    "title": "Example",
                    "published_at": "2026-05-13",
                    "language": "en",
                },
                "entities": [
                    {
                        "entity_id": "entity-1",
                        "canonical_name": "China",
                        "aliases": ["China"],
                        "entity_type": "COUNTRY",
                    }
                ],
                "mentions": [
                    {
                        "mention_id": "mention-1",
                        "entity_id": "entity-1",
                        "normalized_name": "China",
                        "entity_type": "COUNTRY",
                        "text": "China",
                        "sentence": "China met Romania.",
                        "sentence_index": 0,
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (temporals_dir / f"{article_id}.temporals.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "temporal_expressions": [
                    {
                        "temporal_id": "time-1",
                        "text": "yesterday",
                        "kind": "relative_date",
                        "normalized": "2026-05-12",
                        "granularity": "day",
                        "resolved": True,
                        "ambiguous": False,
                        "confidence": 0.95,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (events_dir / f"{article_id}.events.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "events": [
                    {
                        "event_id": "event-1",
                        "event_type": "DiplomaticMeeting",
                        "trigger": "met",
                        "normalized_trigger": "meeting",
                        "sentence": "China met Romania.",
                        "confidence": 0.8,
                        "participant_entity_ids": ["entity-1"],
                        "temporal_id": "time-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (relations_dir / f"{article_id}.relations.json").write_text(
        json.dumps(
            {
                "article_id": article_id,
                "relations": [
                    {
                        "relation_id": "rel-1",
                        "source_id": "entity-1",
                        "target_id": "event-1",
                        "relation_type": "participated_in",
                        "confidence": 0.8,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    connector = FakeConnector()
    KnowledgeGraphLoader(connector=connector).load(
        entities_dir, temporals_dir, events_dir, relations_dir
    )

    assert connector.calls

    rows = [row for _, params in connector.calls for row in params.get("rows", [])]

    assert any(row.get("id") == article_id for row in rows)
    assert any(row.get("entity", {}).get("id") == "entity-1" for row in rows)
    assert any(row.get("event", {}).get("id") == "event-1" for row in rows)
    assert any(row.get("event", {}).get("event_key") for row in rows)
    assert any(row.get("temporal", {}).get("id") == "time-1" for row in rows)

    temporal_params = [
        row.get("temporal", {})
        for row in rows
        if row.get("temporal", {}).get("id") == "time-1"
    ][0]
    assert temporal_params["start_date"] == "2026-05-12"
    assert temporal_params["end_date"] == "2026-05-12"
    assert any(
        row.get("claim", {}).get("event_type") == "DiplomaticMeeting"
        for row in rows
    )
    assert any(
        row.get("relation", {}).get("relation_id") == "rel-1"
        for row in rows
    )
