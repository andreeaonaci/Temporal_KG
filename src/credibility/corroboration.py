"""Transparent corroboration heuristics for event and claim support."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.credibility.scorer import CredibilityScorer
from src.extraction.pipeline_utils import (
    build_claim_signature,
    build_event_signature,
    load_json_by_article,
)
from src.graph.graph_loader import KnowledgeGraphLoader


@dataclass
class EvidenceRecord:
    """Compact evidence for one article-backed event."""

    article_id: str
    event_id: str
    record_type: str
    record_id: str
    record_key: str
    event_type: str
    sentence: str
    source_name: str | None
    source_domain: str | None
    url: str | None
    published_at: str | None
    start_date: str | None
    end_date: str | None


class CorroborationAnalyzer:
    """Aggregate article-level event evidence into support summaries."""

    def __init__(self, scorer: CredibilityScorer | None = None) -> None:
        self._scorer = scorer or CredibilityScorer()

    def analyze_directories(
        self,
        *,
        entities_dir: Path,
        temporals_dir: Path,
        events_dir: Path,
    ) -> dict[str, list[dict[str, Any]]]:
        entity_payloads = load_json_by_article(entities_dir)
        temporal_payloads = load_json_by_article(temporals_dir)
        event_payloads = load_json_by_article(events_dir)

        evidences: list[EvidenceRecord] = []
        for article_id, event_payload in sorted(event_payloads.items()):
            source_article = (
                event_payload.get("source_article")
                or entity_payloads.get(article_id, {}).get("source_article")
                or temporal_payloads.get(article_id, {}).get("source_article")
                or {}
            )
            temporal_map = {
                item["temporal_id"]: KnowledgeGraphLoader._temporal_record(
                    item,
                    article_id,
                )
                for item in temporal_payloads.get(article_id, {}).get(
                    "temporal_expressions",
                    [],
                )
            }
            for event in event_payload.get("events", []):
                temporal = temporal_map.get(event.get("temporal_id"))
                event_key = build_event_signature(
                    event,
                    temporal,
                    start_date=(
                        temporal.get("start_date") if temporal else None
                    ),
                    end_date=(
                        temporal.get("end_date") if temporal else None
                    ),
                )
                claim_key = build_claim_signature(
                    event.get("sentence", ""),
                    event_type=event.get("event_type"),
                    event_signature=event_key,
                )
                evidence = self._build_evidence(
                    article_id=article_id,
                    event=event,
                    source_article=source_article,
                    temporal=temporal,
                    record_type="event",
                    record_id=event["event_id"],
                    record_key=event_key,
                )
                evidences.append(evidence)
                evidences.append(
                    self._build_evidence(
                        article_id=article_id,
                        event=event,
                        source_article=source_article,
                        temporal=temporal,
                        record_type="claim",
                        record_id=f"{event['event_id']}:claim",
                        record_key=claim_key,
                    )
                )

        return {
            "events": self._summarize(
                [item for item in evidences if item.record_type == "event"]
            ),
            "claims": self._summarize(
                [item for item in evidences if item.record_type == "claim"]
            ),
        }

    def write_results(
        self,
        results: dict[str, list[dict[str, Any]]],
        *,
        output_dir: Path,
        stem: str = "corroboration",
    ) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for key, rows in results.items():
            json_path = output_dir / f"{stem}.{key}.json"
            csv_path = output_dir / f"{stem}.{key}.csv"
            json_path.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=sorted(rows[0]) if rows else [],
                )
                if rows:
                    writer.writeheader()
                    writer.writerows(rows)
            paths[f"{key}_json"] = json_path
            paths[f"{key}_csv"] = csv_path
        return paths

    def _build_evidence(
        self,
        *,
        article_id: str,
        event: dict[str, Any],
        source_article: dict[str, Any],
        temporal: dict[str, Any] | None,
        record_type: str,
        record_id: str,
        record_key: str,
    ) -> EvidenceRecord:
        url = source_article.get("url")
        return EvidenceRecord(
            article_id=article_id,
            event_id=event["event_id"],
            record_type=record_type,
            record_id=record_id,
            record_key=record_key,
            event_type=event["event_type"],
            sentence=event.get("sentence", ""),
            source_name=source_article.get("source_name"),
            source_domain=self._source_domain(url),
            url=url,
            published_at=source_article.get("published_at"),
            start_date=temporal.get("start_date") if temporal else None,
            end_date=temporal.get("end_date") if temporal else None,
        )

    def _summarize(
        self,
        evidences: list[EvidenceRecord],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[EvidenceRecord]] = {}
        for evidence in evidences:
            grouped.setdefault(evidence.record_key, []).append(evidence)

        rows: list[dict[str, Any]] = []
        for record_key, items in sorted(grouped.items()):
            source_domains = sorted(
                {item.source_domain for item in items if item.source_domain}
            )
            article_ids = sorted({item.article_id for item in items})
            event_types = sorted(
                {item.event_type for item in items if item.event_type}
            )
            time_windows = sorted(
                {
                    f"{item.start_date or ''}|{item.end_date or ''}"
                    for item in items
                    if item.start_date or item.end_date
                }
            )
            contradiction_flag = len(event_types) > 1 or len(time_windows) > 1
            support_count = len(article_ids)
            source_diversity = len(source_domains)
            repeated_reporting = support_count > 1 and source_diversity > 1
            isolated_claim = support_count == 1 or source_diversity <= 1
            credibility_score = self._credibility_score(
                items,
                support_count=support_count,
                source_diversity=source_diversity,
                contradiction_flag=contradiction_flag,
            )
            rows.append(
                {
                    "record_type": items[0].record_type,
                    "record_key": record_key,
                    "representative_id": items[0].record_id,
                    "event_ids": sorted({item.event_id for item in items}),
                    "article_ids": article_ids,
                    "event_types": event_types,
                    "support_count": support_count,
                    "source_diversity": source_diversity,
                    "source_domains": source_domains,
                    "repeated_reporting": repeated_reporting,
                    "isolated_claim": isolated_claim,
                    "contradiction_flag": contradiction_flag,
                    "time_windows": time_windows,
                    "credibility_score": round(credibility_score, 3),
                    "verification_status": self._verification_status(
                        support_count=support_count,
                        source_diversity=source_diversity,
                        contradiction_flag=contradiction_flag,
                    ),
                    "sample_sentence": items[0].sentence,
                }
            )
        return rows

    def _credibility_score(
        self,
        items: list[EvidenceRecord],
        *,
        support_count: int,
        source_diversity: int,
        contradiction_flag: bool,
    ) -> float:
        domain_scores = [
            self._scorer.score_url(item.url or "")
            for item in items
            if item.url
        ]
        base_score = (
            sum(domain_scores) / len(domain_scores)
            if domain_scores
            else self._scorer._default
        )
        support_bonus = min(0.3, (support_count - 1) * 0.08)
        diversity_bonus = min(0.15, max(0, source_diversity - 1) * 0.05)
        contradiction_penalty = 0.35 if contradiction_flag else 0.0
        final_score = (
            base_score
            + support_bonus
            + diversity_bonus
            - contradiction_penalty
        )
        return max(0.0, min(1.0, final_score))

    @staticmethod
    def _verification_status(
        *,
        support_count: int,
        source_diversity: int,
        contradiction_flag: bool,
    ) -> str:
        if contradiction_flag:
            return "contradictory"
        if support_count >= 3 and source_diversity >= 2:
            return "corroborated"
        if support_count >= 2:
            return "weakly_supported"
        return "unresolved"

    @staticmethod
    def _source_domain(url: str | None) -> str | None:
        if not url:
            return None
        return urlparse(url).netloc.lower().lstrip("www.")
