from __future__ import annotations

from datetime import datetime

from src.extraction.entity_extractor import EntityExtractor
from src.extraction.event_extractor import EventExtractor
from src.extraction.pipeline_utils import stable_id
from src.extraction.relation_extractor import RelationExtractor
from src.temporal.date_normaliser import DateNormaliser
from src.temporal.temporal_extractor import TemporalExtractor

SAMPLE_ARTICLE = {
    "article_id": stable_id("article", "1"),
    "url": "https://example.com/china-romania",
    "title": "China and Romania sign new agreements",
    "published_at": "2026-05-13T10:00:00+00:00",
    "language": "en",
    "content_clean": (
        "President Klaus Iohannis met Foreign Minister Wang Yi in Bucharest yesterday. "
        "China and Romania signed a trade agreement from May to July 2025. "
        "The project will last for 5 years and remains valid until 2030."
    ),
}


def test_entity_extractor_keeps_spans_sentences_and_normalization():
    payload = EntityExtractor().extract_article(SAMPLE_ARTICLE)

    entity_types = {
        (entity["canonical_name"], entity["entity_type"])
        for entity in payload["entities"]
    }
    assert ("Romania", "COUNTRY") in entity_types
    assert ("China", "COUNTRY") in entity_types
    assert any(mention["text"] == "Klaus Iohannis" for mention in payload["mentions"])
    assert all(mention["sentence"] for mention in payload["mentions"])
    assert all(
        mention["end_char"] > mention["start_char"] for mention in payload["mentions"]
    )


def test_date_normaliser_handles_relative_interval_duration_and_deadline():
    ref = datetime(2026, 5, 13)
    normaliser = DateNormaliser()

    assert normaliser.normalise("yesterday", ref)["value"] == "2026-05-12"
    assert normaliser.normalise("from May to July 2025", ref)["value"] == {
        "start": "2025-05",
        "end": "2025-07",
    }
    assert normaliser.normalise("for 5 years", ref)["value"] == "P5Y"
    assert normaliser.normalise("until 2030", ref)["value"] == {"end": "2030"}


def test_temporal_event_and_relation_pipeline_outputs_linked_records():
    temporal_payload = TemporalExtractor().extract_article(SAMPLE_ARTICLE)
    entity_payload = EntityExtractor().extract_article(SAMPLE_ARTICLE)
    event_payload = EventExtractor().extract_article(
        SAMPLE_ARTICLE, entity_payload, temporal_payload
    )
    relation_payload = RelationExtractor().extract_article(
        SAMPLE_ARTICLE,
        entity_payload,
        temporal_payload,
        event_payload,
    )

    assert any(
        item["kind"] == "relative_date"
        for item in temporal_payload["temporal_expressions"]
    )
    assert any(
        event["event_type"] == "DiplomaticMeeting" for event in event_payload["events"]
    )
    assert any(
        event["event_type"] == "TradeAgreement" for event in event_payload["events"]
    )
    assert any(
        rel["relation_type"] == "participated_in"
        for rel in relation_payload["relations"]
    )
    assert any(
        rel["relation_type"] == "signed_with" for rel in relation_payload["relations"]
    )
