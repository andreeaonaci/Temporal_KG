#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Project-local wrapper for DeepKE-style extraction.

This script accepts a simple --input/--output interface so the main pipeline
can run from a separate conda environment even when upstream DeepKE does not
expose a stable console script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)
TITLE_RE = re.compile(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\b")

COUNTRIES = {"china", "romania"}
ORG_SUFFIXES = {
    "ministry",
    "government",
    "commission",
    "parliament",
    "university",
    "company",
    "corp",
    "inc",
    "ltd",
    "bank",
}


def stable_id(*parts: Any) -> str:
    text = "|".join(str(p) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_type(name: str) -> str:
    token = name.strip().lower()
    if token in COUNTRIES:
        return "GPE"
    if any(token.endswith(suffix) for suffix in ORG_SUFFIXES):
        return "ORG"
    if len(name.split()) >= 2:
        return "PERSON"
    return "ENTITY"


def extract_entities(text: str, article_id: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for sentence_index, match in enumerate(SENTENCE_RE.finditer(text)):
        sentence = match.group(0)
        sentence_start = match.start()
        for m in TITLE_RE.finditer(sentence):
            value = m.group(0).strip()
            if len(value) < 3:
                continue
            start = sentence_start + m.start()
            end = sentence_start + m.end()
            key = (start, end, value.lower())
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                {
                    "entity_id": stable_id(article_id, value, start, end),
                    "text": value,
                    "type": detect_type(value),
                    "start": start,
                    "end": end,
                    "sentence_index": sentence_index,
                    "confidence": 0.55,
                }
            )

    return entities


def extract_relations(
    entities: list[dict[str, Any]], article_id: str, text: str
) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    by_sentence: dict[int, list[dict[str, Any]]] = {}
    for entity in entities:
        by_sentence.setdefault(int(entity.get("sentence_index", 0)), []).append(entity)

    for sentence_index, sentence_entities in by_sentence.items():
        if len(sentence_entities) < 2:
            continue
        sentence_text = ""
        sentence_matches = list(SENTENCE_RE.finditer(text))
        if 0 <= sentence_index < len(sentence_matches):
            sentence_text = sentence_matches[sentence_index].group(0).strip()

        limit = min(8, len(sentence_entities))
        for i in range(limit):
            for j in range(i + 1, limit):
                head = sentence_entities[i]
                tail = sentence_entities[j]
                relations.append(
                    {
                        "head_id": head["entity_id"],
                        "tail_id": tail["entity_id"],
                        "relation": "co_mentioned",
                        "sentence": sentence_text,
                        "sentence_index": sentence_index,
                        "confidence": 0.5,
                        "relation_id": stable_id(
                            article_id,
                            "co_mentioned",
                            head["entity_id"],
                            tail["entity_id"],
                            sentence_index,
                        ),
                    }
                )

    return relations


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepKE wrapper for project pipeline.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    article_id = payload.get("id") or payload.get("article_id") or stable_id(args.input)
    text = str(payload.get("text") or "")

    entities = extract_entities(text, article_id)
    relations = extract_relations(entities, article_id, text)

    out = {
        "article_id": article_id,
        "entities": entities,
        "relations": relations,
        "meta": {
            "engine": "deepke_wrapper",
            "entity_count": len(entities),
            "relation_count": len(relations),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
