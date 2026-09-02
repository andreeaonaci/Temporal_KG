#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Precision/recall/F1 of the extraction pipeline against a hand-labeled gold set.

Runs the entity/event extractors twice per gold sentence -- once in "legacy"
mode (spaCy NER and dependency-parse layers disabled, matching the
project's original regex/gazetteer-only behavior) and once in "hybrid" mode
(the current default: spaCy statistical NER ensembled with the gazetteer,
dependency-parse verb/argument matching layered on top of the regex
triggers) -- and reports precision/recall/F1 for both against
``tests/fixtures/gold_eval_set.json``. This is the ablation that quantifies
the entity/event-extraction novelty claim: hybrid vs. legacy, on the same
sentences, same metric.

Usage:
    python scripts/evaluate_extraction.py
    python scripts/evaluate_extraction.py --gold-set tests/fixtures/gold_eval_set.json
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.entity_extractor import EntityExtractor  # noqa: E402
from src.extraction.event_extractor import EventExtractor  # noqa: E402
from src.extraction.pipeline_utils import stable_id  # noqa: E402
from src.utils.config import settings  # noqa: E402

DEFAULT_GOLD_SET = PROJECT_ROOT / "tests" / "fixtures" / "gold_eval_set.json"


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, predicted: set, gold: set) -> None:
        self.tp += len(predicted & gold)
        self.fp += len(predicted - gold)
        self.fn += len(gold - predicted)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_row(self, label: str) -> str:
        return f"{label:<22} P={self.precision:.3f}  R={self.recall:.3f}  F1={self.f1:.3f}  (tp={self.tp} fp={self.fp} fn={self.fn})"


def _load_gold(path: Path) -> list[dict[str, Any]]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["items"]


def _article_for(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "article_id": stable_id("gold_eval", item["id"]),
        "url": None,
        "title": None,
        "published_at": None,
        "language": "en",
        "content_clean": item["text"],
    }


def _normalize_entity_text(text: str) -> str:
    return " ".join(text.lower().split())


def run_mode(items: list[dict[str, Any]], *, use_spacy_ner: bool, use_dependency_parse: bool) -> dict[str, PRF]:
    """Run the pipeline once with the given feature flags and score it against gold."""
    entity_extractor = EntityExtractor()
    entity_extractor._use_spacy_ner = use_spacy_ner  # noqa: SLF001 (test-only override)
    event_extractor = EventExtractor()
    event_extractor._use_dependency_parse = use_dependency_parse  # noqa: SLF001

    entity_scores = PRF()
    event_scores = PRF()

    for item in items:
        article = _article_for(item)
        entity_payload = entity_extractor.extract_article(article)
        event_payload = event_extractor.extract_article(
            article, entity_payload, {"temporal_expressions": []}
        )

        predicted_entities = {
            (_normalize_entity_text(e["canonical_name"]), e["entity_type"])
            for e in entity_payload["entities"]
        }
        gold_entities = {
            (_normalize_entity_text(e["text"]), e["type"]) for e in item["entities"]
        }
        entity_scores.add(predicted_entities, gold_entities)

        predicted_events = {e["event_type"] for e in event_payload["events"]}
        gold_events = set(item["event_types"])
        event_scores.add(predicted_events, gold_events)

    return {"entities": entity_scores, "events": event_scores}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate extraction precision/recall/F1 against the gold set."
    )
    parser.add_argument("--gold-set", type=Path, default=DEFAULT_GOLD_SET)
    args = parser.parse_args()

    items = _load_gold(args.gold_set)
    print(f"Loaded {len(items)} gold items from {args.gold_set}\n")

    legacy = run_mode(items, use_spacy_ner=False, use_dependency_parse=False)
    hybrid = run_mode(items, use_spacy_ner=True, use_dependency_parse=True)

    print("=== Entity extraction ===")
    print(legacy["entities"].as_row("legacy (gazetteer)"))
    print(hybrid["entities"].as_row("hybrid (+ spaCy NER)"))
    print()
    print("=== Event-type extraction ===")
    print(legacy["events"].as_row("legacy (regex-only)"))
    print(hybrid["events"].as_row("hybrid (+ dep-parse)"))
    print()
    print(
        "Note: if spaCy / en_core_web_sm is not installed in the running "
        "environment, both extractors silently fall back to their regex-only "
        "path (see settings.extraction.use_spacy_ner / use_dependency_parse), "
        "and the two rows above will be identical -- that is a setup problem, "
        "not a null result."
    )


if __name__ == "__main__":
    main()
