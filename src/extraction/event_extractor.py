# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Event extraction for bilateral China-Romania news."""

from __future__ import annotations

import re
from typing import Any

from src.extraction.pipeline_utils import dependency_argument_mentions, stable_id
from src.ontology.taxonomy import annotate_event
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

EVENT_RULES = {
    "DiplomaticMeeting": {
        "triggers": [
            r"\bmet\b",
            r"\bmeet(?:ing|s)?\b",
            r"\btalks?\b",
            r"\bsummit\b",
            r"\bvisit(?:ed|s)?\b",
            r"\bdiscuss(?:ed|es|ion)?\b",
            r"\bîntâln(?:ire|it|esc)\b",
            r"\bdiscuții\b",
        ],
        "lemma_triggers": {"meet", "visit", "discuss", "talk", "consult"},
        "normalized_trigger": "meeting",
    },
    "TradeAgreement": {
        "triggers": [
            r"\btrade agreement\b",
            r"\bsigned?\b",
            r"\bdeal\b",
            r"\bmemorandum\b",
            r"\baccord\b",
            r"\bacord\b",
            r"\bsemnat\b",
        ],
        "lemma_triggers": {"sign", "agree"},
        "normalized_trigger": "agreement",
    },
    "InvestmentProject": {
        "triggers": [
            r"\binvest(?:ment|ed|s)?\b",
            r"\bproject\b",
            r"\bfinanc(?:e|ed|ing)\b",
            r"\bbuild(?:ing|s)?\b",
        ],
        "lemma_triggers": {"invest", "fund", "finance"},
        "normalized_trigger": "investment",
    },
    "TechnologyCooperation": {
        "triggers": [
            r"\btechnology\b",
            r"\btech\b",
            r"\bresearch\b",
            r"\binnovation\b",
            r"\bdigital\b",
            r"\bai\b",
            r"\bartificial intelligence\b",
        ],
        "lemma_triggers": {"research", "innovate", "collaborate", "cooperate"},
        "normalized_trigger": "technology_cooperation",
    },
    "InfrastructureProject": {
        "triggers": [
            r"\binfrastructure\b",
            r"\bhighway\b",
            r"\bbridge\b",
            r"\bport\b",
            r"\brail\b",
            r"\benergy\b",
            r"\bpower plant\b",
        ],
        "lemma_triggers": {"build", "construct", "expand"},
        "normalized_trigger": "infrastructure_project",
    },
    "EducationCooperation": {
        "triggers": [
            r"\beducation\b",
            r"\buniversity\b",
            r"\bscholarship\b",
            r"\bstudent exchange\b",
            r"\btraining\b",
        ],
        "lemma_triggers": {"study", "train", "educate"},
        "normalized_trigger": "education_cooperation",
    },
    "SecurityStatement": {
        "triggers": [
            r"\bsecurity\b",
            r"\bdefense\b",
            r"\bmilitary\b",
            r"\barmed forces\b",
            r"\bnational security\b",
        ],
        "lemma_triggers": {"threaten", "warn", "defend"},
        "normalized_trigger": "security_statement",
    },
    "SanctionOrRestriction": {
        "triggers": [
            r"\bsanction\b",
            r"\brestriction\b",
            r"\bexport control\b",
            r"\bblacklist\b",
            r"\bban\b",
        ],
        "lemma_triggers": {"sanction", "restrict", "ban", "blacklist"},
        "normalized_trigger": "sanction_or_restriction",
    },
    "CompanyActivity": {
        "triggers": [
            r"\bcompany\b",
            r"\bfirm\b",
            r"\bsubsidiary\b",
            r"\bplant\b",
            r"\bopened\b",
            r"\bexpansion\b",
        ],
        "lemma_triggers": {"open", "launch", "operate"},
        "normalized_trigger": "company_activity",
    },
    "CulturalExchange": {
        "triggers": [
            r"\bcultural\b",
            r"\bexchange\b",
            r"\bexhibition\b",
            r"\bfestival\b",
            r"\beducational\b",
            r"\bculturală\b",
            r"\bcultural\b",
        ],
        "lemma_triggers": {"exchange", "celebrate", "exhibit"},
        "normalized_trigger": "cultural_exchange",
    },
    "PolicyStatement": {
        "triggers": [
            r"\bannounced?\b",
            r"\bsaid\b",
            r"\bstatement\b",
            r"\bdeclared?\b",
            r"\burged?\b",
            r"\bpolicy\b",
            r"\banunțat\b",
            r"\bdeclarat\b",
        ],
        "lemma_triggers": {"announce", "say", "declare", "state", "urge"},
        "normalized_trigger": "policy_statement",
    },
}

class EventExtractor:
    """Extract compact event records from sentence-level cues.

    Two extraction layers run in sequence:

    1. Dependency-parse layer (``_extract_events_dependency``): fires a
       trigger only on a verb *lemma* match (not a raw substring anywhere in
       the sentence) and restricts participants to entities that are actual
       syntactic arguments of that verb. Requires a loaded spaCy pipeline
       with a parser/lemmatizer (``en_core_web_sm`` or better).
    2. Regex fallback layer (``_extract_events_regex``, the original
       implementation): keyword/substring matching over the whole sentence.
       Always runs, but skips any (sentence, event_type) pair the dependency
       layer already produced, so it only fills gaps -- e.g. non-English
       sentences (the Romanian trigger patterns), or when spaCy is
       unavailable, in which case it is the sole extraction path.
    """

    def __init__(self) -> None:
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
            if not self._nlp.has_pipe("parser") or not self._nlp.has_pipe("lemmatizer"):
                log.info(
                    "spaCy model '%s' has no parser/lemmatizer; "
                    "dependency-based event extraction disabled",
                    self._model,
                )
                self._nlp = False
        except Exception as exc:
            log.info(
                "Dependency parser unavailable (%s); falling back to regex trigger matching",
                exc,
            )
            self._nlp = False

    def extract_article(
        self,
        article: dict[str, Any],
        entity_payload: dict[str, Any],
        temporal_payload: dict[str, Any],
    ) -> dict[str, Any]:
        article_id = article["article_id"]
        mentions = entity_payload.get("mentions", [])
        temporals = temporal_payload.get("temporal_expressions", [])

        sentence_entities: dict[int, list[dict[str, Any]]] = {}
        for mention in mentions:
            sentence_entities.setdefault(mention["sentence_index"], []).append(mention)

        sentence_temporals: dict[int, list[dict[str, Any]]] = {}
        for temporal in temporals:
            sentence_temporals.setdefault(temporal["sentence_index"], []).append(
                temporal
            )

        self._load_model()
        events: list[dict[str, Any]] = []
        if self._nlp:
            text = article.get("content_clean") or ""
            events.extend(
                self._extract_events_dependency(
                    text, article_id, sentence_entities, sentence_temporals
                )
            )

        already_covered = {(e["sentence_index"], e["event_type"]) for e in events}
        events.extend(
            self._extract_events_regex(
                article_id, mentions, sentence_entities, sentence_temporals, already_covered
            )
        )
        return {
            "article_id": article_id,
            "source_article": article,
            "events": events,
        }

    def _extract_events_dependency(
        self,
        text: str,
        article_id: str,
        sentence_entities: dict[int, list[dict[str, Any]]],
        sentence_temporals: dict[int, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if not text or not text.strip():
            return []
        events: list[dict[str, Any]] = []
        doc = self._nlp(text)
        for sentence_index, sent in enumerate(doc.sents):
            sentence_text = sent.text.strip()
            if not sentence_text:
                continue
            sentence_mentions = sentence_entities.get(sentence_index, [])
            sentence_temporal = sentence_temporals.get(sentence_index, [])
            seen_types: set[str] = set()
            for token in sent:
                if token.pos_ not in ("VERB", "AUX"):
                    continue
                event_type = self._match_lemma_trigger(token.lemma_.lower())
                if not event_type or event_type in seen_types:
                    continue
                config = EVENT_RULES[event_type]
                arg_entity_ids = self._syntactic_arguments(token, sentence_mentions)
                participants = sorted(
                    arg_entity_ids or {m["entity_id"] for m in sentence_mentions}
                )
                confidence = 0.66 + min(0.24, len(participants) * 0.05)
                if arg_entity_ids:
                    confidence += 0.08
                if sentence_temporal:
                    confidence += 0.04
                event_id = stable_id(article_id, event_type, sentence_index, token.lemma_)
                event_record = {
                    "event_id": event_id,
                    "article_id": article_id,
                    "event_type": event_type,
                    "trigger": token.text,
                    "normalized_trigger": config["normalized_trigger"],
                    "sentence": sentence_text,
                    "sentence_index": sentence_index,
                    "participant_entity_ids": participants,
                    "temporal_id": (
                        sentence_temporal[0]["temporal_id"] if sentence_temporal else None
                    ),
                    "confidence": round(min(confidence, 0.97), 3),
                    "extraction_method": "dependency_parse",
                }
                events.append(annotate_event(event_record))
                seen_types.add(event_type)
        return events

    @staticmethod
    def _match_lemma_trigger(lemma: str) -> str | None:
        for event_type, config in EVENT_RULES.items():
            if lemma in config.get("lemma_triggers", ()):
                return event_type
        return None

    @staticmethod
    def _syntactic_arguments(
        token: Any, sentence_mentions: list[dict[str, Any]]
    ) -> set[str]:
        """Return entity_ids of mentions overlapping a core argument of *token*."""
        grouped = dependency_argument_mentions(token, sentence_mentions)
        return {
            mention["entity_id"] for mentions in grouped.values() for mention in mentions
        }

    def _extract_events_regex(
        self,
        article_id: str,
        mentions: list[dict[str, Any]],
        sentence_entities: dict[int, list[dict[str, Any]]],
        sentence_temporals: dict[int, list[dict[str, Any]]],
        already_covered: set[tuple[int, str]] = frozenset(),
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        processed_sentences = sorted(set(sentence_entities) | set(sentence_temporals))
        for sentence_index in processed_sentences:
            sentence_mentions = sentence_entities.get(sentence_index, [])
            sentence_temporal = sentence_temporals.get(sentence_index, [])
            sentence = (
                sentence_mentions[0]["sentence"]
                if sentence_mentions
                else sentence_temporal[0]["sentence"]
            )
            lowered = sentence.lower()
            for event_type, config in EVENT_RULES.items():
                if (sentence_index, event_type) in already_covered:
                    continue
                trigger = self._find_trigger(lowered, config["triggers"])
                if not trigger:
                    continue
                participants = sorted(
                    {mention["entity_id"] for mention in sentence_mentions}
                )
                confidence = 0.62 + min(0.28, len(participants) * 0.06)
                if sentence_temporal:
                    confidence += 0.05
                event_id = stable_id(article_id, event_type, sentence_index, trigger)
                event_record = {
                    "event_id": event_id,
                    "article_id": article_id,
                    "event_type": event_type,
                    "trigger": trigger,
                    "normalized_trigger": config["normalized_trigger"],
                    "sentence": sentence,
                    "sentence_index": sentence_index,
                    "participant_entity_ids": participants,
                    "temporal_id": (
                        sentence_temporal[0]["temporal_id"]
                        if sentence_temporal
                        else None
                    ),
                    "confidence": round(min(confidence, 0.97), 3),
                    "extraction_method": "regex_trigger",
                }
                events.append(annotate_event(event_record))
        return events

    @staticmethod
    def _find_trigger(sentence: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, sentence, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return None
