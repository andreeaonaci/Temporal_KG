# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Sentence-level relation extraction using extracted entities and events."""

from __future__ import annotations

import re
import json
from typing import Any

from src.extraction.pipeline_utils import dependency_argument_mentions, stable_id
from src.extraction.deepke_adapter import normalize_relations
from src.extraction.deepke_client import DeepKEClient
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_SUBJECT_DEPS = {"nsubj", "nsubjpass"}
_OBJECT_DEPS = {"dobj", "pobj", "attr", "dative", "oprd"}


class RelationExtractor:
    """Create a small stable set of relations from entities and events."""

    def __init__(self) -> None:
        self._use_deepke = bool(settings("extraction.use_deepke", False))
        self._deepke_client = DeepKEClient()
        self._nlp: Any = None
        self._model = settings("extraction.spacy_model", "en_core_web_sm")
        self._use_dependency_parse = bool(
            settings("extraction.use_dependency_parse", True)
        )

    def _load_model(self) -> None:
        if self._nlp is not None:
            return
        if not self._use_dependency_parse:
            self._nlp = False
            return
        try:
            import spacy

            self._nlp = spacy.load(self._model)
            if not self._nlp.has_pipe("parser"):
                self._nlp = False
        except Exception as exc:
            log.info(
                "Dependency parser unavailable (%s); skipping syntactic-relation extraction",
                exc,
            )
            self._nlp = False

    def extract_article(
        self,
        article: dict[str, Any],
        entity_payload: dict[str, Any],
        temporal_payload: dict[str, Any],
        event_payload: dict[str, Any],
    ) -> dict[str, Any]:
        article_id = article["article_id"]
        entities = {
            entity["entity_id"]: entity for entity in entity_payload.get("entities", [])
        }
        mentions_by_sentence: dict[int, list[dict[str, Any]]] = {}
        for mention in entity_payload.get("mentions", []):
            mentions_by_sentence.setdefault(mention["sentence_index"], []).append(
                mention
            )

        temporals_by_sentence: dict[int, list[dict[str, Any]]] = {}
        for temporal in temporal_payload.get("temporal_expressions", []):
            temporals_by_sentence.setdefault(temporal["sentence_index"], []).append(
                temporal
            )

        relations: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, int]] = set()

        for event in event_payload.get("events", []):
            sentence_index = event["sentence_index"]
            sentence = event["sentence"]
            participants = event.get("participant_entity_ids", [])
            for entity_id in participants:
                seen_key = (
                    entity_id,
                    "participated_in",
                    event["event_id"],
                    sentence_index,
                )
                if seen_key in seen:
                    continue
                seen.add(seen_key)
                relations.append(
                    self._build_relation(
                        article_id,
                        "participated_in",
                        entity_id,
                        "entity",
                        event["event_id"],
                        "event",
                        sentence,
                        sentence_index,
                        event_id=event["event_id"],
                        temporal_id=event.get("temporal_id"),
                        confidence=event["confidence"],
                    )
                )

            if event["event_type"] == "TradeAgreement" and len(participants) >= 2:
                pair = participants[:2]
                relations.append(
                    self._build_relation(
                        article_id,
                        "signed_with",
                        pair[0],
                        "entity",
                        pair[1],
                        "entity",
                        sentence,
                        sentence_index,
                        event_id=event["event_id"],
                        temporal_id=event.get("temporal_id"),
                        confidence=0.84,
                    )
                )
            if event["event_type"] == "InvestmentProject" and len(participants) >= 2:
                pair = participants[:2]
                relations.append(
                    self._build_relation(
                        article_id,
                        "invested_in",
                        pair[0],
                        "entity",
                        pair[1],
                        "entity",
                        sentence,
                        sentence_index,
                        event_id=event["event_id"],
                        temporal_id=event.get("temporal_id"),
                        confidence=0.8,
                    )
                )
            if event["event_type"] == "PolicyStatement" and participants:
                relations.append(
                    self._build_relation(
                        article_id,
                        "announced_by",
                        event["event_id"],
                        "event",
                        participants[0],
                        "entity",
                        sentence,
                        sentence_index,
                        event_id=event["event_id"],
                        temporal_id=event.get("temporal_id"),
                        confidence=0.82,
                    )
                )

        for sentence_index, mentions in mentions_by_sentence.items():
            sentence = mentions[0]["sentence"]
            locations = [
                mention
                for mention in mentions
                if mention["entity_type"] in {"LOCATION", "COUNTRY"}
            ]
            orgs = [
                mention
                for mention in mentions
                if mention["entity_type"] in {"ORGANIZATION", "PERSON"}
            ]
            if re.search(
                r"\bhosted by\b|\bgăzduit de\b|\bgazduit de\b",
                sentence,
                flags=re.IGNORECASE,
            ):
                events = [
                    event
                    for event in event_payload.get("events", [])
                    if event["sentence_index"] == sentence_index
                ]
                if events and orgs:
                    relations.append(
                        self._build_relation(
                            article_id,
                            "hosted_by",
                            events[0]["event_id"],
                            "event",
                            orgs[0]["entity_id"],
                            "entity",
                            sentence,
                            sentence_index,
                            event_id=events[0]["event_id"],
                            temporal_id=events[0].get("temporal_id"),
                            confidence=0.78,
                        )
                    )
            if (
                locations
                and orgs
                and re.search(
                    r"\b(in|at|from|din|în|la)\b", sentence, flags=re.IGNORECASE
                )
            ):
                relations.append(
                    self._build_relation(
                        article_id,
                        "located_in",
                        orgs[0]["entity_id"],
                        "entity",
                        locations[0]["entity_id"],
                        "entity",
                        sentence,
                        sentence_index,
                        temporal_id=(
                            temporals_by_sentence.get(sentence_index, [{}])[0].get(
                                "temporal_id"
                            )
                            if temporals_by_sentence.get(sentence_index)
                            else None
                        ),
                        confidence=0.76,
                    )
                )

        self._load_model()
        if self._nlp:
            text = article.get("content_clean") or ""
            relations.extend(
                self._extract_syntactic_relations(text, article_id, mentions_by_sentence)
            )

        relations.extend(self._deepke_relations(article_id))

        return {
            "article_id": article_id,
            "source_article": article,
            "relations": relations,
            "entity_index": entities,
        }

    def _extract_syntactic_relations(
        self,
        text: str,
        article_id: str,
        mentions_by_sentence: dict[int, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Open (subject, predicate, object) triples read off the dependency parse.

        Complements the event-type-keyed templated relations above (which
        only fire for a handful of hand-picked event types) with a general
        mechanism: any verb whose subject and object both resolve to a known
        entity mention produces a relation, typed by the verb's lemma rather
        than a fixed vocabulary.
        """
        if not text or not text.strip():
            return []
        relations: list[dict[str, Any]] = []
        doc = self._nlp(text)
        for sentence_index, sent in enumerate(doc.sents):
            sentence_mentions = mentions_by_sentence.get(sentence_index, [])
            if len(sentence_mentions) < 2:
                continue
            sentence_text = sent.text.strip()
            if not sentence_text:
                continue
            for token in sent:
                if token.pos_ not in ("VERB", "AUX"):
                    continue
                grouped = dependency_argument_mentions(token, sentence_mentions)
                subjects = [
                    mention
                    for dep, mentions in grouped.items()
                    if dep in _SUBJECT_DEPS
                    for mention in mentions
                ]
                objects = [
                    mention
                    for dep, mentions in grouped.items()
                    if dep in _OBJECT_DEPS
                    for mention in mentions
                ]
                if not subjects or not objects:
                    continue
                predicate = token.lemma_.lower()
                for subject in subjects:
                    for obj in objects:
                        if subject["entity_id"] == obj["entity_id"]:
                            continue
                        relations.append(
                            self._build_relation(
                                article_id,
                                f"syntactic:{predicate}",
                                subject["entity_id"],
                                "entity",
                                obj["entity_id"],
                                "entity",
                                sentence_text,
                                sentence_index,
                                confidence=0.72,
                            )
                        )
        return relations

    def _deepke_relations(self, article_id: str) -> list[dict[str, Any]]:
        if not (self._use_deepke and self._deepke_client.enabled()):
            return []
        output_path = self._deepke_client.output_path(article_id)
        if not output_path.exists():
            return []
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return normalize_relations(payload, article_id=article_id)

    @staticmethod
    def _build_relation(
        article_id: str,
        relation_type: str,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        sentence: str,
        sentence_index: int,
        event_id: str | None = None,
        temporal_id: str | None = None,
        confidence: float = 0.75,
    ) -> dict[str, Any]:
        return {
            "relation_id": stable_id(
                article_id, relation_type, source_id, target_id, sentence_index
            ),
            "article_id": article_id,
            "relation_type": relation_type,
            "source_id": source_id,
            "source_type": source_type,
            "target_id": target_id,
            "target_type": target_type,
            "sentence": sentence,
            "sentence_index": sentence_index,
            "event_id": event_id,
            "temporal_id": temporal_id,
            "confidence": round(confidence, 3),
        }
