# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.temporal.time_bucket_gate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A rule-based reproduction of the core idea behind Allein et al. (EACL 2023,
"Implicit Temporal Reasoning for Evidence-Based Fact-Checking"): ground two
dated texts in time by the *distance* between their dates, quantized into
buckets, rather than by their exact qualitative relation.

Allein et al. learn a time-bucket embedding per distance-in-days bucket
(their paper uses 20 data-driven quantiles) and let a neural fact-checking
model consume it as a feature -- a genuinely different, more expressive
mechanism than what's reproduced here. What IS comparable, and what this
module isolates for a fair ablation, is the underlying *temporal
representation*: coarse distance-bucket membership, not the exact
before/after/meets/overlaps/equals relation Allen's algebra computes. This
lets ``evaluate_temporal_contradiction.py`` answer a real question a
reviewer familiar with that paper would ask: does the extra precision of
full interval-algebra reasoning (src/temporal/reasoner.py) actually earn
its complexity over simply asking "are these two dates close together"?

Not a full reproduction (no learned embeddings, no neural model, no access
to their training data) -- a fair, honest, same-mechanism-class rule-based
stand-in for the ablation that question requires.
"""

from __future__ import annotations

from src.temporal.reasoner import _parse_date

# Bucket boundaries in days. Coarser than Allen's algebra deliberately --
# the point of this baseline is to show what's lost by not knowing the
# *exact* relation (touching vs. properly overlapping vs. containing),
# only the rough distance.
_SAME_DAY = 0
_SAME_WEEK = 7
_SAME_MONTH = 31
_SAME_QUARTER = 92

BUCKET_ORDER = ("same_day", "same_week", "same_month", "same_quarter", "beyond")


def bucket_distance(date_a: str | None, date_b: str | None) -> str:
    """Return the coarse time-bucket for the distance between two dates.

    Returns "unknown" if either date can't be parsed -- distinct from
    "beyond" (parsed but far apart), matching reasoner.compare_ranges'
    "unknown" convention for unresolvable dates.
    """
    parsed_a = _parse_date(date_a)
    parsed_b = _parse_date(date_b)
    if parsed_a is None or parsed_b is None:
        return "unknown"

    distance_days = abs((parsed_a - parsed_b).days)
    if distance_days <= _SAME_DAY:
        return "same_day"
    if distance_days <= _SAME_WEEK:
        return "same_week"
    if distance_days <= _SAME_MONTH:
        return "same_month"
    if distance_days <= _SAME_QUARTER:
        return "same_quarter"
    return "beyond"


def is_temporally_close(
    date_a: str | None, date_b: str | None, *, within: str = "same_week"
) -> bool:
    """Return True if the two dates fall within *within* buckets of each other.

    Unknown dates are treated as NOT close -- no temporal evidence to
    justify treating them as coincident, mirroring reasoner.py's
    conservative fallback for missing dates.
    """
    bucket = bucket_distance(date_a, date_b)
    if bucket == "unknown":
        return False
    return BUCKET_ORDER.index(bucket) <= BUCKET_ORDER.index(within)
