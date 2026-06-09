from __future__ import annotations

from src.graph.query_layer import TemporalGraphQueries


class FakeConnector:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query: str, **params):
        self.calls.append((query, params))
        return self.rows


def test_events_query_builds_overlap_and_filters():
    connector = FakeConnector(
        rows=[
            {
                "event_id": "event-1",
                "temporal_value": (
                    '{"start": "2025-05-01", "end": "2025-05-31"}'
                ),
                "entities": [{"id": "entity-1", "canonical_name": "China"}],
            }
        ]
    )
    queries = TemporalGraphQueries(connector=connector)

    rows = queries.events_within_date_range(
        start_date="2025-05",
        end_date="2025-12",
        source="reuters",
        entity="China",
        event_type="DiplomaticMeeting",
    )

    assert rows[0]["temporal_value"]["start"] == "2025-05-01"
    query, params = connector.calls[0]
    assert "$start_date" in query
    assert "$end_date" in query
    assert params["start_date"] == "2025-05-01"
    assert params["end_date"] == "2025-12-31"
    assert params["source"] == "reuters"
    assert params["entity"] == "china"
    assert params["event_type"] == "diplomaticmeeting"


def test_articles_supporting_event_uses_event_key_lookup():
    connector = FakeConnector(rows=[{"article_id": "article-1"}])
    queries = TemporalGraphQueries(connector=connector)

    rows = queries.articles_supporting_event("event-1")

    assert rows == [{"article_id": "article-1"}]
    query, params = connector.calls[0]
    assert "seed.event_key" in query
    assert params["event_id"] == "event-1"
