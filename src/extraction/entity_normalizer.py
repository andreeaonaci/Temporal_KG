# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Entity normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedEntity:
    text: str
    canonical_name: str
    entity_type: str
    confidence: float


class EntityNormaliser:
    """Normalize entity mentions to stable canonical names."""

    COUNTRY_ALIASES = {
        "china": "China",
        "prc": "China",
        "people s republic of china": "China",
        "people republic of china": "China",
        "chinese": "China",
        "romania": "Romania",
        "romanian": "Romania",
        "româniei": "Romania",
        "românia": "Romania",
        "republic of china": "China",
    }

    LOCATION_ALIASES = {
        "beijing": "Beijing",
        "bucharest": "Bucharest",
        "bucurești": "Bucharest",
        "bucuresti": "Bucharest",
        "shanghai": "Shanghai",
        "cluj-napoca": "Cluj-Napoca",
        "cluj napoca": "Cluj-Napoca",
        "timișoara": "Timișoara",
        "timisoara": "Timișoara",
        "constanța": "Constanța",
        "constanta": "Constanța",
    }

    def normalise(self, text: str, entity_type: str) -> NormalizedEntity:
        cleaned = self._clean(text)
        key = self._key(cleaned)

        if entity_type == "COUNTRY":
            canonical = self.COUNTRY_ALIASES.get(key, cleaned)
            confidence = 0.99 if key in self.COUNTRY_ALIASES else 0.85
        elif entity_type == "LOCATION":
            canonical = self.LOCATION_ALIASES.get(key, cleaned)
            confidence = 0.96 if key in self.LOCATION_ALIASES else 0.82
        else:
            canonical = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
            confidence = 0.9 if canonical == cleaned else 0.84

        return NormalizedEntity(
            text=text,
            canonical_name=canonical,
            entity_type=entity_type,
            confidence=confidence,
        )

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
    def _key(text: str) -> str:
        ascii_text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()
