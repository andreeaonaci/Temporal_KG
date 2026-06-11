# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Claim verification and fake-news heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.credibility.corroboration import CorroborationAnalyzer
from src.credibility.scorer import CredibilityScorer
from src.temporal.reasoner import detect_temporal_inconsistencies


@dataclass
class ClaimAssessment:
    record_key: str
    verification_status: str
    credibility_score: float
    support_count: int
    source_diversity: int
    contradiction_flag: bool
    temporal_issues: list[dict[str, Any]]


class ClaimVerifier:
    """Aggregate corroboration and temporal checks into a verification label."""

    def __init__(self) -> None:
        self._corroboration = CorroborationAnalyzer()
        self._scorer = CredibilityScorer()

    def assess(
        self,
        *,
        entities_dir,
        temporals_dir,
        events_dir,
    ) -> list[ClaimAssessment]:
        results = self._corroboration.analyze_directories(
            entities_dir=entities_dir,
            temporals_dir=temporals_dir,
            events_dir=events_dir,
        )
        claims = results.get("claims", [])
        assessments: list[ClaimAssessment] = []

        temporal_issues = detect_temporal_inconsistencies(
            [event for event in results.get("events", [])]
        )
        temporal_issue_map = {
            issue.get("event_id"): issue for issue in temporal_issues
        }

        for claim in claims:
            score = float(claim.get("credibility_score", 0.0))
            support = int(claim.get("support_count", 0))
            diversity = int(claim.get("source_diversity", 0))
            contradiction = bool(claim.get("contradiction_flag", False))
            status = claim.get("verification_status", "unknown")
            record_key = claim.get("record_key", "")

            issues = []
            for event_id in claim.get("event_ids", []):
                if event_id in temporal_issue_map:
                    issues.append(temporal_issue_map[event_id])

            if contradiction or issues:
                status = "contested"
            elif support >= 2 and diversity >= 2 and score >= 0.6:
                status = "corroborated"
            elif support <= 1 or diversity <= 1:
                status = "unverified"

            assessments.append(
                ClaimAssessment(
                    record_key=record_key,
                    verification_status=status,
                    credibility_score=score,
                    support_count=support,
                    source_diversity=diversity,
                    contradiction_flag=contradiction,
                    temporal_issues=issues,
                )
            )
        return assessments
