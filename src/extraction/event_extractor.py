"""Event extraction for bilateral China-Romania news."""

from __future__ import annotations

import re
from typing import Any

from src.extraction.pipeline_utils import stable_id
from src.ontology.taxonomy import annotate_event

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
        "normalized_trigger": "agreement",
    },
    "InvestmentProject": {
        "triggers": [
            r"\binvest(?:ment|ed|s)?\b",
            r"\bproject\b",
            r"\bfinanc(?:e|ed|ing)\b",
            r"\bbuild(?:ing|s)?\b",
            r"\binfrastructur(?:e|ă)\b",
        ],
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
        "normalized_trigger": "policy_statement",
    },
}


class EventExtractor:
    """Extract compact event records from sentence-level cues."""

    def extract_article(
        self,
        article: dict[str, Any],
        entity_payload: dict[str, Any],
        temporal_payload: dict[str, Any],
    ) -> dict[str, Any]:
        article_id = article["article_id"]
        mentions = entity_payload.get("mentions", [])
        temporals = temporal_payload.get("temporal_expressions", [])
        events: list[dict[str, Any]] = []

        sentence_entities: dict[int, list[dict[str, Any]]] = {}
        for mention in mentions:
            sentence_entities.setdefault(mention["sentence_index"], []).append(mention)

        sentence_temporals: dict[int, list[dict[str, Any]]] = {}
        for temporal in temporals:
            sentence_temporals.setdefault(temporal["sentence_index"], []).append(
                temporal
            )

        processed_sentences = sorted(
            {mention["sentence_index"] for mention in mentions}
            | {temporal["sentence_index"] for temporal in temporals}
        )
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
                }
                events.append(annotate_event(event_record))
        return {
            "article_id": article_id,
            "source_article": article,
            "events": events,
        }

    @staticmethod
    def _find_trigger(sentence: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, sentence, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return None
