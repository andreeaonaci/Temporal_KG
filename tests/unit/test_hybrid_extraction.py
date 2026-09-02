# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for the hybrid spaCy-NER / dependency-parse extraction layers.

Tests that require a real spaCy pipeline (``en_core_web_sm``) are skipped
when it is unavailable, via ``pytest.importorskip``, so this file still runs
-- and still verifies the regex/gazetteer fallback path -- in environments
without the model installed.
"""

from __future__ import annotations

import pytest

from src.extraction.entity_extractor import EntityExtractor
from src.extraction.event_extractor import EventExtractor
from src.extraction.pipeline_utils import stable_id
from src.extraction.relation_extractor import RelationExtractor

SAMPLE_ARTICLE = {
    "article_id": stable_id("article", "hybrid-1"),
    "url": "https://example.com/china-romania-hybrid",
    "title": "Xi met Romanian officials in Bucharest",
    "published_at": "2026-05-13T10:00:00+00:00",
    "language": "en",
    "content_clean": (
        "Xi met Romanian officials in Bucharest on Monday. "
        "China and Romania signed a new investment agreement worth millions."
    ),
}


def _spacy_with_parser_available() -> bool:
    spacy = pytest.importorskip("spacy")
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        pytest.skip("en_core_web_sm not installed")
    return nlp.has_pipe("parser") and nlp.has_pipe("lemmatizer")


def test_entity_extractor_regex_fallback_still_works_without_spacy_ner():
    extractor = EntityExtractor()
    extractor._use_spacy_ner = False  # noqa: SLF001
    payload = extractor.extract_article(SAMPLE_ARTICLE)
    canonical_names = {e["canonical_name"] for e in payload["entities"]}
    assert "Romania" in canonical_names
    assert "China" in canonical_names


def test_event_extractor_regex_layer_tags_extraction_method():
    entity_payload = EntityExtractor().extract_article(SAMPLE_ARTICLE)
    extractor = EventExtractor()
    extractor._use_dependency_parse = False  # noqa: SLF001
    event_payload = extractor.extract_article(
        SAMPLE_ARTICLE, entity_payload, {"temporal_expressions": []}
    )
    assert event_payload["events"], "regex fallback should still find events"
    assert all(e["extraction_method"] == "regex_trigger" for e in event_payload["events"])


def test_event_extractor_dependency_layer_skips_gracefully_without_spacy(monkeypatch):
    """When spaCy is unavailable, dependency mode degrades to regex-only, not a crash."""
    extractor = EventExtractor()
    extractor._use_dependency_parse = True  # noqa: SLF001
    entity_payload = EntityExtractor().extract_article(SAMPLE_ARTICLE)
    # Should not raise even if spaCy/en_core_web_sm is not installed here.
    event_payload = extractor.extract_article(
        SAMPLE_ARTICLE, entity_payload, {"temporal_expressions": []}
    )
    assert isinstance(event_payload["events"], list)


def test_hybrid_ner_recovers_single_token_person_name():
    _spacy_with_parser_available()
    extractor = EntityExtractor()
    payload = extractor.extract_article(SAMPLE_ARTICLE)
    person_names = {
        m["text"] for m in payload["mentions"] if m["entity_type"] == "PERSON"
    }
    # "Xi" is a single token: the gazetteer-only path (2-token minimum for
    # PERSON) can never produce it; only the spaCy-NER ensemble layer can.
    assert "Xi" in person_names


def test_dependency_event_extraction_restricts_participants_to_syntactic_arguments():
    _spacy_with_parser_available()
    entity_payload = EntityExtractor().extract_article(SAMPLE_ARTICLE)
    event_payload = EventExtractor().extract_article(
        SAMPLE_ARTICLE, entity_payload, {"temporal_expressions": []}
    )
    dependency_events = [
        e for e in event_payload["events"] if e["extraction_method"] == "dependency_parse"
    ]
    assert dependency_events, "dependency layer should fire on 'met' and 'signed'"
    diplomatic = [e for e in dependency_events if e["event_type"] == "DiplomaticMeeting"]
    assert diplomatic
    assert diplomatic[0]["participant_entity_ids"], "meeting event should have participants"


def test_relation_extractor_produces_syntactic_triple():
    _spacy_with_parser_available()
    entity_payload = EntityExtractor().extract_article(SAMPLE_ARTICLE)
    event_payload = EventExtractor().extract_article(
        SAMPLE_ARTICLE, entity_payload, {"temporal_expressions": []}
    )
    relation_payload = RelationExtractor().extract_article(
        SAMPLE_ARTICLE, entity_payload, {"temporal_expressions": []}, event_payload
    )
    syntactic = [
        r for r in relation_payload["relations"] if r["relation_type"].startswith("syntactic:")
    ]
    assert syntactic, "open dependency-parse triples should be produced for a two-entity sentence"
