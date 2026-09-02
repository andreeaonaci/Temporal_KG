# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

from src.temporal.time_bucket_gate import bucket_distance, is_temporally_close


def test_same_day_is_same_day_bucket():
    assert bucket_distance("2025-06-01", "2025-06-01") == "same_day"


def test_within_a_week_is_same_week_bucket():
    assert bucket_distance("2025-06-01", "2025-06-05") == "same_week"


def test_within_a_month_is_same_month_bucket():
    assert bucket_distance("2025-06-01", "2025-06-20") == "same_month"


def test_within_a_quarter_is_same_quarter_bucket():
    assert bucket_distance("2025-06-01", "2025-08-15") == "same_quarter"


def test_far_apart_is_beyond():
    assert bucket_distance("2025-01-01", "2026-01-01") == "beyond"


def test_unparseable_date_is_unknown_not_beyond():
    assert bucket_distance("not-a-date", "2025-06-01") == "unknown"
    assert bucket_distance(None, "2025-06-01") == "unknown"


def test_bucket_distance_is_symmetric():
    assert bucket_distance("2025-06-01", "2025-06-20") == bucket_distance("2025-06-20", "2025-06-01")


def test_is_temporally_close_respects_within_threshold():
    assert is_temporally_close("2025-06-01", "2025-06-03", within="same_week") is True
    assert is_temporally_close("2025-06-01", "2025-07-15", within="same_week") is False
    assert is_temporally_close("2025-06-01", "2025-07-15", within="same_quarter") is True


def test_is_temporally_close_treats_unknown_as_not_close():
    assert is_temporally_close("not-a-date", "2025-06-01") is False
