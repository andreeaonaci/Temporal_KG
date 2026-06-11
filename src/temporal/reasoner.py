# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Temporal reasoning helpers for event timelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TemporalRelation:
    source_event_id: str
    target_event_id: str
    relation: str
    reason: str


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10])
    except ValueError:
        return None


def compare_ranges(
    start_a: str | None,
    end_a: str | None,
    start_b: str | None,
    end_b: str | None,
) -> str:
    """Return a qualitative temporal relation between two ranges."""
    a_start = _parse_date(start_a)
    a_end = _parse_date(end_a) or a_start
    b_start = _parse_date(start_b)
    b_end = _parse_date(end_b) or b_start

    if not a_start or not b_start:
        return "unknown"
    if a_end and b_start and a_end < b_start:
        return "before"
    if b_end and a_start and b_end < a_start:
        return "after"
    if a_start <= b_start and a_end and b_end and a_end >= b_end:
        return "contains"
    if b_start <= a_start and a_end and b_end and b_end >= a_end:
        return "during"
    return "overlaps"


def build_temporal_relations(
    events: list[dict[str, Any]],
) -> list[TemporalRelation]:
    """Build pairwise temporal relations for event timelines."""
    relations: list[TemporalRelation] = []
    for i, left in enumerate(events):
        for right in events[i + 1 :]:
            relation = compare_ranges(
                left.get("start_date"),
                left.get("end_date"),
                right.get("start_date"),
                right.get("end_date"),
            )
            relations.append(
                TemporalRelation(
                    source_event_id=left.get("event_id") or left.get("id") or "",
                    target_event_id=right.get("event_id") or right.get("id") or "",
                    relation=relation,
                    reason="range_comparison",
                )
            )
    return relations


def detect_temporal_inconsistencies(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flag events with invalid temporal ranges or missing anchors."""
    issues: list[dict[str, Any]] = []
    for event in events:
        start = event.get("start_date")
        end = event.get("end_date")
        start_dt = _parse_date(start)
        end_dt = _parse_date(end)
        if start_dt and end_dt and end_dt < start_dt:
            issues.append(
                {
                    "event_id": event.get("event_id") or event.get("id"),
                    "issue": "end_before_start",
                    "start_date": start,
                    "end_date": end,
                }
            )
        if not start_dt and not end_dt:
            issues.append(
                {
                    "event_id": event.get("event_id") or event.get("id"),
                    "issue": "missing_temporal_bounds",
                    "start_date": start,
                    "end_date": end,
                }
            )
    return issues
