# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Temporal reasoning helpers for event timelines.

Implements Allen's Interval Algebra (Allen, 1983, "Maintaining Knowledge
about Temporal Intervals") -- the standard formalism for qualitative
reasoning about how two time intervals relate. The previous version of this
module only distinguished 5 coarse buckets (before/after/contains/
during/overlaps, with everything else -- touching intervals, shared
endpoints, exact equality -- silently collapsed into "overlaps"), which
under-serves the "temporal KG reasoning" claim this project makes: two
intervals that share an endpoint (`meets`) are a materially different
relationship from two that genuinely overlap, and conflating them loses
information a real KG consumer would want. This module now implements the
full 13-relation algebra, with the earlier 5-bucket behavior available via
``coarsen_relation`` for any call site that only needs the coarse view.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# The 13 mutually-exclusive, jointly-exhaustive relations between two
# intervals A=[s1,e1] and B=[s2,e2] (s1<=e1, s2<=e2). Named per Allen's
# original paper; each has a named inverse (e.g. "before"/"after"),
# except "equals" which is its own inverse.
ALLEN_RELATIONS = frozenset(
    {
        "before",
        "after",
        "meets",
        "met_by",
        "overlaps",
        "overlapped_by",
        "starts",
        "started_by",
        "during",
        "contains",
        "finishes",
        "finished_by",
        "equals",
    }
)

# Collapses the 13-relation algebra down to the project's original 5-bucket
# view, for callers that only need the coarse distinction.
_COARSE_RELATION = {
    "before": "before",
    "meets": "before",
    "after": "after",
    "met_by": "after",
    "contains": "contains",
    "finished_by": "contains",
    "started_by": "contains",
    "during": "during",
    "finishes": "during",
    "starts": "during",
    "equals": "equals",
    "overlaps": "overlaps",
    "overlapped_by": "overlaps",
}


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


def coarsen_relation(relation: str) -> str:
    """Map one of the 13 Allen relations onto the project's original
    5-bucket view (before/after/contains/during/equals/overlaps)."""
    return _COARSE_RELATION.get(relation, relation)


def allen_relation(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> str:
    """Return the exact Allen relation between two closed intervals.

    Both intervals must already be resolved (non-None) datetimes with
    start <= end; a point-in-time event is represented as start == end.

    Allen's algebra is defined for proper (non-degenerate) intervals, so a
    point event that coincides with another interval's start satisfies both
    "meets" (end_a == start_b) and "starts" (start_a == start_b)
    simultaneously -- a genuine ambiguity, not a bug. The check order below
    resolves it deterministically to "meets" (touching-boundary checks run
    before same-start checks) -- *except* full equality, which is checked
    first: two point events on the same date (start_a == end_a == start_b
    == end_b) would otherwise satisfy "meets" too (end_a == start_b
    trivially, since both equal the same value), which is wrong -- they're
    not touching, they're identical, and that distinction matters a great
    deal to a caller reasoning about whether two same-day reports coincide.
    """
    if end_a < start_b:
        return "before"
    if start_a > end_b:
        return "after"
    if start_a == start_b and end_a == end_b:
        return "equals"
    if end_a == start_b:
        return "meets"
    if start_a == end_b:
        return "met_by"
    if start_a == start_b:
        return "starts" if end_a < end_b else "started_by"
    if end_a == end_b:
        return "finishes" if start_a > start_b else "finished_by"
    if start_a < start_b:
        return "overlaps" if end_a < end_b else "contains"
    # start_a > start_b
    return "overlapped_by" if end_a > end_b else "during"


def compare_ranges(
    start_a: str | None,
    end_a: str | None,
    start_b: str | None,
    end_b: str | None,
) -> str:
    """Return the exact Allen relation between two date ranges, or "unknown"
    if either range's start date can't be resolved. A missing end date is
    treated as a point event (end == start), matching event records that
    only carry a single reported date.
    """
    a_start = _parse_date(start_a)
    a_end = _parse_date(end_a) or a_start
    b_start = _parse_date(start_b)
    b_end = _parse_date(end_b) or b_start

    if not a_start or not b_start:
        return "unknown"
    return allen_relation(a_start, a_end, b_start, b_end)


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
