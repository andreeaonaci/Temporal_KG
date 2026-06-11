# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""End-to-end evaluation orchestration."""

from __future__ import annotations

from typing import Any

from src.evaluation.gold_loader import GoldDataLoader
from src.evaluation.metrics import (
    compute_precision_recall_f1,
    compute_temporal_accuracy,
)
from src.extraction.pipeline_utils import stable_json


class EvaluationPipeline:
    """Compare predicted outputs against a manually annotated subset."""

    def __init__(self, loader: GoldDataLoader | None = None) -> None:
        self._loader = loader or GoldDataLoader()

    def evaluate(
        self,
        *,
        gold_bundle: dict[str, dict[str, dict[str, Any]]],
        predicted_bundle: dict[str, dict[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        article_ids = sorted(
            set(gold_bundle["entities"])
            | set(gold_bundle["temporals"])
            | set(gold_bundle["events"])
            | set(gold_bundle["relations"])
        )
        per_article: list[dict[str, Any]] = []
        entity_pred_all: set[tuple[Any, ...]] = set()
        entity_gold_all: set[tuple[Any, ...]] = set()
        event_pred_all: set[tuple[Any, ...]] = set()
        event_gold_all: set[tuple[Any, ...]] = set()
        relation_pred_all: set[tuple[Any, ...]] = set()
        relation_gold_all: set[tuple[Any, ...]] = set()
        temporal_pred_all: dict[tuple[Any, ...], Any] = {}
        temporal_gold_all: dict[tuple[Any, ...], Any] = {}

        for article_id in article_ids:
            gold_entities = self._entity_items(
                gold_bundle["entities"].get(article_id, {})
            )
            pred_entities = self._entity_items(
                predicted_bundle["entities"].get(article_id, {})
            )
            gold_events = self._event_items(
                gold_bundle["events"].get(article_id, {})
            )
            pred_events = self._event_items(
                predicted_bundle["events"].get(article_id, {})
            )
            gold_relations = self._relation_items(
                gold_bundle["relations"].get(article_id, {})
            )
            pred_relations = self._relation_items(
                predicted_bundle["relations"].get(article_id, {})
            )
            gold_temporals = self._temporal_items(
                gold_bundle["temporals"].get(article_id, {})
            )
            pred_temporals = self._temporal_items(
                predicted_bundle["temporals"].get(article_id, {})
            )

            entity_pred_all |= pred_entities
            entity_gold_all |= gold_entities
            event_pred_all |= pred_events
            event_gold_all |= gold_events
            relation_pred_all |= pred_relations
            relation_gold_all |= gold_relations
            temporal_pred_all.update(pred_temporals)
            temporal_gold_all.update(gold_temporals)

            per_article.append(
                {
                    "article_id": article_id,
                    "entities": compute_precision_recall_f1(
                        pred_entities,
                        gold_entities,
                    ),
                    "events": compute_precision_recall_f1(
                        pred_events,
                        gold_events,
                    ),
                    "relations": compute_precision_recall_f1(
                        pred_relations,
                        gold_relations,
                    ),
                    "temporals": compute_temporal_accuracy(
                        pred_temporals,
                        gold_temporals,
                    ),
                    "case_study": self._case_study(
                        article_id=article_id,
                        gold_events=gold_events,
                        pred_events=pred_events,
                        gold_relations=gold_relations,
                        pred_relations=pred_relations,
                    ),
                }
            )

        summary = {
            "entities": compute_precision_recall_f1(
                entity_pred_all,
                entity_gold_all,
            ),
            "events": compute_precision_recall_f1(
                event_pred_all,
                event_gold_all,
            ),
            "relations": compute_precision_recall_f1(
                relation_pred_all,
                relation_gold_all,
            ),
            "temporals": compute_temporal_accuracy(
                temporal_pred_all,
                temporal_gold_all,
            ),
            "graph_population": {
                "precision": 1.0 if event_pred_all else 0.0,
                "recall": 1.0 if event_gold_all <= event_pred_all else 0.0,
                "f1": 1.0 if event_gold_all == event_pred_all else 0.0,
            },
        }
        return {"summary": summary, "per_article": per_article}

    @staticmethod
    def _entity_items(payload: dict[str, Any]) -> set[tuple[Any, ...]]:
        return {
            (
                item.get("entity_type") or item.get("type"),
                (
                    item.get("canonical_name")
                    or item.get("normalized_name")
                    or ""
                )
                .strip()
                .lower(),
            )
            for item in payload.get("entities", [])
        }

    @staticmethod
    def _event_items(payload: dict[str, Any]) -> set[tuple[Any, ...]]:
        return {
            (
                item.get("event_type"),
                item.get("normalized_trigger"),
                tuple(sorted(item.get("participant_entity_ids", []))),
                item.get("temporal_id"),
            )
            for item in payload.get("events", [])
        }

    @staticmethod
    def _relation_items(payload: dict[str, Any]) -> set[tuple[Any, ...]]:
        return {
            (
                item.get("relation_type"),
                item.get("source_id"),
                item.get("target_id"),
            )
            for item in payload.get("relations", [])
        }

    @staticmethod
    def _temporal_items(payload: dict[str, Any]) -> dict[tuple[Any, ...], Any]:
        return {
            (
                item.get("text", "").lower(),
                item.get("sentence_index"),
            ): stable_json(item.get("normalized"))
            for item in payload.get("temporal_expressions", [])
        }

    @staticmethod
    def _case_study(
        *,
        article_id: str,
        gold_events: set[tuple[Any, ...]],
        pred_events: set[tuple[Any, ...]],
        gold_relations: set[tuple[Any, ...]],
        pred_relations: set[tuple[Any, ...]],
    ) -> dict[str, Any]:
        return {
            "article_id": article_id,
            "missing_events": sorted(gold_events - pred_events),
            "extra_events": sorted(pred_events - gold_events),
            "missing_relations": sorted(gold_relations - pred_relations),
            "extra_relations": sorted(pred_relations - gold_relations),
        }
