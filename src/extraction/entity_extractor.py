# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Entity extraction and article-level entity export helpers."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
import json
from typing import Any

from src.extraction.entity_normalizer import EntityNormaliser
from src.extraction.deepke_adapter import normalize_entities
from src.extraction.deepke_client import DeepKEClient
from src.extraction.pipeline_utils import get_article_id, stable_id
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

ORG_KEYWORDS = (
    "ministry",
    "ministerul",
    "government",
    "guvernul",
    "parliament",
    "parlamentul",
    "embassy",
    "universit",
    "bank",
    "banca",
    "company",
    "consiliul",
    "commission",
    "comisia",
    "council",
    "camera de",
    "agency",
    "institut",
    "administration",
    "administra",
    "forum",
)
PERSON_TITLES = (
    "president",
    "prime minister",
    "foreign minister",
    "minister",
    "ambassador",
    "chairman",
    "secretary",
    "premier",
    "președintele",
    "presedintele",
    "prim-ministrul",
    "prim ministrul",
    "ministrul",
    "ambasadorul",
)
COUNTRY_ALIASES = {
    "China": {
        "China",
        "Chinese",
        "PRC",
        "People's Republic of China",
        "People’s Republic of China",
    },
    "Romania": {"Romania", "Romanian", "România", "României"},
}
LOCATION_ALIASES = {
    "Beijing",
    "Bucharest",
    "București",
    "Bucuresti",
    "Shanghai",
    "Shenzhen",
    "Guangzhou",
    "Cluj",
    "Cluj-Napoca",
    "Timișoara",
    "Timisoara",
    "Iași",
    "Iasi",
    "Constanța",
    "Constanta",
    "Brașov",
    "Brasov",
    "Sibiu",
    "Oradea",
    "Craiova",
    "Ploiești",
    "Ploiesti",
}
SENTENCE_PATTERN = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)
CAPITALIZED_PATTERN = re.compile(
    r"\b[A-ZȘȚĂÂÎ][\w'’\-]+(?:\s+[A-ZȘȚĂÂÎ][\w'’\-]+){0,3}\b"
)
UPPERCASE_PATTERN = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})*\b")
DATE_LABELS = set(
    settings("extraction.entity_types", ["PERSON", "ORG", "GPE", "LOC", "DATE"])
)


@dataclass
class ExtractedEntity:
    text: str
    label: str
    start_char: int = 0
    end_char: int = 0
    confidence: float = 1.0


@dataclass
class EntityMention:
    mention_id: str
    entity_id: str
    article_id: str
    text: str
    normalized_name: str
    entity_type: str
    sentence: str
    sentence_index: int
    start_char: int
    end_char: int
    confidence: float


class EntityExtractor:
    """Rule-first extractor that keeps exact spans and article provenance."""

    def __init__(self) -> None:
        self._normaliser = EntityNormaliser()
        self._nlp: Any = None
        self._model = settings("extraction.spacy_model", "en_core_web_sm")
        self._use_deepke = bool(settings("extraction.use_deepke", False))
        self._deepke_client = DeepKEClient()

    def _load_model(self) -> None:
        if self._nlp is not None:
            return
        try:
            import spacy

            try:
                self._nlp = spacy.load(self._model)
            except Exception:
                self._nlp = spacy.blank("xx")
                if "sentencizer" not in self._nlp.pipe_names:
                    self._nlp.add_pipe("sentencizer")
        except Exception as exc:
            log.warning(
                "spaCy unavailable, falling back to regex sentence splitter: %s", exc
            )
            self._nlp = False

    def extract(self, text: str) -> list[ExtractedEntity]:
        mentions = self._extract_mentions(text, article_id="standalone")
        return [
            ExtractedEntity(
                text=mention.text,
                label=self._legacy_label(mention.entity_type),
                start_char=mention.start_char,
                end_char=mention.end_char,
                confidence=mention.confidence,
            )
            for mention in mentions
        ]

    def extract_article(self, article: dict[str, Any]) -> dict[str, Any]:
        text = article.get("content_clean") or ""
        article_id = get_article_id(article)
        mentions = self._extract_mentions(text, article_id=article_id)
        if self._use_deepke and self._deepke_client.enabled():
            mentions = self._merge_deepke_mentions(
                article_id,
                text,
                mentions,
            )
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for mention in mentions:
            key = (mention.entity_type, mention.normalized_name)
            if key not in merged:
                merged[key] = {
                    "entity_id": mention.entity_id,
                    "canonical_name": mention.normalized_name,
                    "entity_type": mention.entity_type,
                    "aliases": [],
                    "article_ids": [article_id],
                    "mention_ids": [],
                    "mention_count": 0,
                    "confidence": mention.confidence,
                }
            entity = merged[key]
            if mention.text not in entity["aliases"]:
                entity["aliases"].append(mention.text)
            entity["mention_ids"].append(mention.mention_id)
            entity["mention_count"] += 1
            entity["confidence"] = max(entity["confidence"], mention.confidence)

        return {
            "article_id": article_id,
            "source_article": {
                "article_id": article_id,
                "url": article.get("url"),
                "title": article.get("title"),
                "published_at": article.get("published_at"),
                "language": article.get("language"),
            },
            "entities": list(merged.values()),
            "mentions": [asdict(mention) for mention in mentions],
        }

    def _merge_deepke_mentions(
        self,
        article_id: str,
        text: str,
        base_mentions: list[EntityMention],
    ) -> list[EntityMention]:
        output_path = self._deepke_client.output_path(article_id)
        if not output_path.exists():
            log.warning("DeepKE output missing for %s", article_id)
            return base_mentions

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        sentence_lookup = {
            index: {"sentence": sentence, "start": start}
            for sentence, index, start in self._iter_sentences(text)
        }
        _, deepke_mentions = normalize_entities(
            payload,
            article_id=article_id,
            sentence_lookup=sentence_lookup,
        )

        merged_mentions: list[EntityMention] = list(base_mentions)
        for mention in deepke_mentions:
            merged_mentions.append(
                EntityMention(
                    mention_id=mention["mention_id"],
                    entity_id=mention["entity_id"],
                    article_id=mention["article_id"],
                    text=mention["text"],
                    normalized_name=mention["normalized_name"],
                    entity_type=mention["entity_type"],
                    sentence=mention.get("sentence", ""),
                    sentence_index=int(mention.get("sentence_index", 0)),
                    start_char=int(mention.get("start_char", 0)),
                    end_char=int(mention.get("end_char", 0)),
                    confidence=float(mention.get("confidence", 0.7)),
                )
            )

        return merged_mentions

    def _extract_mentions(self, text: str, article_id: str) -> list[EntityMention]:
        if not text or not text.strip():
            return []

        mentions: list[EntityMention] = []
        seen_spans: set[tuple[int, int, str]] = set()
        for sentence_text, sentence_index, sentence_start in self._iter_sentences(text):
            mentions.extend(
                self._extract_country_mentions(
                    sentence_text,
                    sentence_index,
                    sentence_start,
                    article_id,
                    seen_spans,
                )
            )
            mentions.extend(
                self._extract_location_mentions(
                    sentence_text,
                    sentence_index,
                    sentence_start,
                    article_id,
                    seen_spans,
                )
            )
            mentions.extend(
                self._extract_title_people(
                    sentence_text,
                    sentence_index,
                    sentence_start,
                    article_id,
                    seen_spans,
                )
            )
            mentions.extend(
                self._extract_org_mentions(
                    sentence_text,
                    sentence_index,
                    sentence_start,
                    article_id,
                    seen_spans,
                )
            )
            mentions.extend(
                self._extract_capitalized_people(
                    sentence_text,
                    sentence_index,
                    sentence_start,
                    article_id,
                    seen_spans,
                )
            )
        return sorted(
            mentions,
            key=lambda item: (item.start_char, item.end_char, item.entity_type),
        )

    def _iter_sentences(self, text: str) -> list[tuple[str, int, int]]:
        self._load_model()
        if self._nlp and self._nlp is not False:
            doc = self._nlp(text)
            return [
                (sent.text.strip(), index, sent.start_char)
                for index, sent in enumerate(doc.sents)
                if sent.text.strip()
            ]

        matches = []
        for index, match in enumerate(SENTENCE_PATTERN.finditer(text)):
            sentence = match.group(0).strip()
            if sentence:
                matches.append((sentence, index, match.start()))
        return matches

    def _extract_country_mentions(
        self,
        sentence: str,
        sentence_index: int,
        sentence_start: int,
        article_id: str,
        seen_spans: set[tuple[int, int, str]],
    ) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        for canonical_name, aliases in COUNTRY_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                pattern = re.compile(
                    rf"(?<!\w){re.escape(alias)}(?!\w)", re.IGNORECASE | re.UNICODE
                )
                for match in pattern.finditer(sentence):
                    mentions.append(
                        self._build_mention(
                            article_id,
                            sentence,
                            sentence_index,
                            sentence_start,
                            match.start(),
                            match.end(),
                            "COUNTRY",
                            seen_spans,
                            override_name=canonical_name,
                        )
                    )
        return [mention for mention in mentions if mention]

    def _extract_location_mentions(
        self,
        sentence: str,
        sentence_index: int,
        sentence_start: int,
        article_id: str,
        seen_spans: set[tuple[int, int, str]],
    ) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        for name in sorted(LOCATION_ALIASES, key=len, reverse=True):
            pattern = re.compile(
                rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE | re.UNICODE
            )
            for match in pattern.finditer(sentence):
                mention = self._build_mention(
                    article_id,
                    sentence,
                    sentence_index,
                    sentence_start,
                    match.start(),
                    match.end(),
                    "LOCATION",
                    seen_spans,
                )
                if mention:
                    mentions.append(mention)
        return mentions

    def _extract_title_people(
        self,
        sentence: str,
        sentence_index: int,
        sentence_start: int,
        article_id: str,
        seen_spans: set[tuple[int, int, str]],
    ) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        name_pattern = re.compile(r"[A-ZȘȚĂÂÎ][\w'’\-]+(?:\s+[A-ZȘȚĂÂÎ][\w'’\-]+){1,2}")
        for title in PERSON_TITLES:
            title_pattern = re.compile(
                rf"\b{re.escape(title)}\b", re.IGNORECASE | re.UNICODE
            )
            for title_match in title_pattern.finditer(sentence):
                name_start = title_match.end()
                while name_start < len(sentence) and sentence[name_start].isspace():
                    name_start += 1
                name_match = name_pattern.match(sentence, name_start)
                if not name_match:
                    continue
                mention = self._build_mention(
                    article_id,
                    sentence,
                    sentence_index,
                    sentence_start,
                    name_match.start(),
                    name_match.end(),
                    "PERSON",
                    seen_spans,
                    confidence=0.93,
                )
                if mention:
                    mentions.append(mention)
        return mentions

    def _extract_org_mentions(
        self,
        sentence: str,
        sentence_index: int,
        sentence_start: int,
        article_id: str,
        seen_spans: set[tuple[int, int, str]],
    ) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        for match in CAPITALIZED_PATTERN.finditer(sentence):
            candidate = match.group(0).strip()
            lowered = candidate.lower()
            if any(keyword in lowered for keyword in ORG_KEYWORDS):
                mention = self._build_mention(
                    article_id,
                    sentence,
                    sentence_index,
                    sentence_start,
                    match.start(),
                    match.end(),
                    "ORGANIZATION",
                    seen_spans,
                    confidence=0.9,
                )
                if mention:
                    mentions.append(mention)
        for match in UPPERCASE_PATTERN.finditer(sentence):
            candidate = match.group(0).strip()
            if len(candidate) >= 2 and candidate not in {"PRC"}:
                mention = self._build_mention(
                    article_id,
                    sentence,
                    sentence_index,
                    sentence_start,
                    match.start(),
                    match.end(),
                    "ORGANIZATION",
                    seen_spans,
                    confidence=0.78,
                )
                if mention:
                    mentions.append(mention)
        return mentions

    def _extract_capitalized_people(
        self,
        sentence: str,
        sentence_index: int,
        sentence_start: int,
        article_id: str,
        seen_spans: set[tuple[int, int, str]],
    ) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        for match in CAPITALIZED_PATTERN.finditer(sentence):
            candidate = match.group(0).strip()
            if self._should_skip_person_candidate(candidate):
                continue
            mention = self._build_mention(
                article_id,
                sentence,
                sentence_index,
                sentence_start,
                match.start(),
                match.end(),
                "PERSON",
                seen_spans,
                confidence=0.74,
            )
            if mention:
                mentions.append(mention)
        return mentions

    def _build_mention(
        self,
        article_id: str,
        sentence: str,
        sentence_index: int,
        sentence_start: int,
        local_start: int,
        local_end: int,
        entity_type: str,
        seen_spans: set[tuple[int, int, str]],
        confidence: float | None = None,
        override_name: str | None = None,
    ) -> EntityMention | None:
        start_char = sentence_start + local_start
        end_char = sentence_start + local_end
        span_key = (start_char, end_char, entity_type)
        if span_key in seen_spans:
            return None

        text = sentence[local_start:local_end].strip(" ,.;:()[]{}\"'")
        if not text:
            return None
        if entity_type == "PERSON" and len(text.split()) < 2:
            return None
        normalized = self._normaliser.normalise(override_name or text, entity_type)
        seen_spans.add(span_key)
        return EntityMention(
            mention_id=stable_id(article_id, entity_type, text, start_char, end_char),
            entity_id=stable_id(entity_type, normalized.canonical_name),
            article_id=article_id,
            text=text,
            normalized_name=normalized.canonical_name,
            entity_type=entity_type,
            sentence=sentence.strip(),
            sentence_index=sentence_index,
            start_char=start_char,
            end_char=end_char,
            confidence=round(confidence or normalized.confidence, 3),
        )

    @staticmethod
    def _legacy_label(entity_type: str) -> str:
        return {
            "PERSON": "PERSON",
            "ORGANIZATION": "ORG",
            "LOCATION": "LOC",
            "COUNTRY": "GPE",
        }.get(entity_type, entity_type)

    @staticmethod
    def _should_skip_person_candidate(candidate: str) -> bool:
        lowered = candidate.lower()
        if any(lowered.startswith(title) for title in PERSON_TITLES):
            return True
        if any(
            candidate.lower() == alias.lower()
            for aliases in COUNTRY_ALIASES.values()
            for alias in aliases
        ):
            return True
        if candidate in LOCATION_ALIASES:
            return True
        if any(keyword in lowered for keyword in ORG_KEYWORDS):
            return True
        if candidate.isupper() and len(candidate) <= 5:
            return True
        return len(candidate.split()) < 2
