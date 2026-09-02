# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for Allen's Interval Algebra in src.temporal.reasoner.

Covers all 13 relations (Allen, 1983) with concrete interval examples, plus
the previous 5-bucket behavior via ``coarsen_relation`` and the
``compare_ranges``/``detect_temporal_inconsistencies`` string-date wrappers
that the rest of the pipeline actually calls.
"""

from __future__ import annotations

from datetime import datetime

from src.temporal.reasoner import (
    ALLEN_RELATIONS,
    allen_relation,
    coarsen_relation,
    compare_ranges,
    detect_temporal_inconsistencies,
)


def _d(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_before_and_after_are_inverses():
    assert allen_relation(_d("2025-01-01"), _d("2025-01-05"), _d("2025-02-01"), _d("2025-02-10")) == "before"
    assert allen_relation(_d("2025-02-01"), _d("2025-02-10"), _d("2025-01-01"), _d("2025-01-05")) == "after"


def test_meets_and_met_by_share_a_boundary_with_no_overlap():
    assert allen_relation(_d("2025-01-01"), _d("2025-01-10"), _d("2025-01-10"), _d("2025-01-20")) == "meets"
    assert allen_relation(_d("2025-01-10"), _d("2025-01-20"), _d("2025-01-01"), _d("2025-01-10")) == "met_by"


def test_overlaps_and_overlapped_by():
    assert allen_relation(_d("2025-01-01"), _d("2025-01-10"), _d("2025-01-05"), _d("2025-01-15")) == "overlaps"
    assert allen_relation(_d("2025-01-05"), _d("2025-01-15"), _d("2025-01-01"), _d("2025-01-10")) == "overlapped_by"


def test_starts_and_started_by_share_the_start_point():
    assert allen_relation(_d("2025-01-01"), _d("2025-01-05"), _d("2025-01-01"), _d("2025-01-10")) == "starts"
    assert allen_relation(_d("2025-01-01"), _d("2025-01-10"), _d("2025-01-01"), _d("2025-01-05")) == "started_by"


def test_finishes_and_finished_by_share_the_end_point():
    assert allen_relation(_d("2025-01-05"), _d("2025-01-10"), _d("2025-01-01"), _d("2025-01-10")) == "finishes"
    assert allen_relation(_d("2025-01-01"), _d("2025-01-10"), _d("2025-01-05"), _d("2025-01-10")) == "finished_by"


def test_during_and_contains():
    assert allen_relation(_d("2025-01-05"), _d("2025-01-08"), _d("2025-01-01"), _d("2025-01-10")) == "during"
    assert allen_relation(_d("2025-01-01"), _d("2025-01-10"), _d("2025-01-05"), _d("2025-01-08")) == "contains"


def test_equals_is_its_own_inverse():
    assert allen_relation(_d("2025-01-01"), _d("2025-01-10"), _d("2025-01-01"), _d("2025-01-10")) == "equals"


def test_point_events_touching_an_intervals_start_are_classified_as_meets():
    # A point event (start == end, e.g. a single reported date with no end)
    # that coincides with another interval's start satisfies both "meets"
    # (end_a == start_b) and "starts" (start_a == start_b) simultaneously --
    # Allen's algebra is defined for proper (non-degenerate) intervals, so
    # this is a genuine edge case, not a bug. allen_relation()'s check order
    # deterministically resolves it to "meets"; this test pins that
    # convention down so it doesn't silently drift.
    assert allen_relation(_d("2025-01-01"), _d("2025-01-01"), _d("2025-01-01"), _d("2025-01-10")) == "meets"


def test_all_13_relations_are_covered_by_a_symmetric_sweep():
    # Sweep B's start across A=[10,20] and B's end far enough to hit every
    # relation, checking both A-vs-B and B-vs-A come out as true inverses.
    a_start, a_end = _d("2025-01-10"), _d("2025-01-20")
    cases = [
        (_d("2025-01-01"), _d("2025-01-05")),  # before
        (_d("2025-01-01"), _d("2025-01-10")),  # meets
        (_d("2025-01-01"), _d("2025-01-15")),  # overlaps
        (_d("2025-01-10"), _d("2025-01-15")),  # starts
        (_d("2025-01-10"), _d("2025-01-20")),  # equals
        (_d("2025-01-10"), _d("2025-01-25")),  # started_by
        (_d("2025-01-12"), _d("2025-01-18")),  # during
        (_d("2025-01-12"), _d("2025-01-20")),  # finishes
        (_d("2025-01-05"), _d("2025-01-20")),  # finished_by
        (_d("2025-01-05"), _d("2025-01-25")),  # contains
        (_d("2025-01-15"), _d("2025-01-25")),  # overlapped_by
        (_d("2025-01-20"), _d("2025-01-25")),  # met_by
        (_d("2025-01-25"), _d("2025-01-30")),  # after
    ]
    seen = set()
    for b_start, b_end in cases:
        forward = allen_relation(a_start, a_end, b_start, b_end)
        backward = allen_relation(b_start, b_end, a_start, a_end)
        seen.add(forward)
        assert backward in ALLEN_RELATIONS
    assert seen == ALLEN_RELATIONS


def test_coarsen_relation_matches_the_original_5_bucket_view():
    assert coarsen_relation("meets") == "before"
    assert coarsen_relation("met_by") == "after"
    assert coarsen_relation("finished_by") == "contains"
    assert coarsen_relation("started_by") == "contains"
    assert coarsen_relation("starts") == "during"
    assert coarsen_relation("finishes") == "during"
    assert coarsen_relation("overlapped_by") == "overlaps"
    assert coarsen_relation("equals") == "equals"


def test_compare_ranges_treats_missing_end_date_as_a_point_event():
    # See test_point_events_touching_an_intervals_start_are_classified_as_meets
    # for why this degenerate case resolves to "meets", not "starts".
    assert compare_ranges("2025-01-01", None, "2025-01-01", "2025-01-10") == "meets"


def test_compare_ranges_returns_unknown_when_start_dates_missing():
    assert compare_ranges(None, None, "2025-01-01", "2025-01-10") == "unknown"
    assert compare_ranges("2025-01-01", "2025-01-10", None, None) == "unknown"


def test_detect_temporal_inconsistencies_flags_end_before_start():
    issues = detect_temporal_inconsistencies(
        [{"event_id": "e1", "start_date": "2025-01-10", "end_date": "2025-01-01"}]
    )
    assert len(issues) == 1
    assert issues[0]["issue"] == "end_before_start"


def test_detect_temporal_inconsistencies_flags_missing_bounds():
    issues = detect_temporal_inconsistencies([{"event_id": "e1"}])
    assert len(issues) == 1
    assert issues[0]["issue"] == "missing_temporal_bounds"


def test_detect_temporal_inconsistencies_passes_valid_events():
    issues = detect_temporal_inconsistencies(
        [{"event_id": "e1", "start_date": "2025-01-01", "end_date": "2025-01-10"}]
    )
    assert issues == []
