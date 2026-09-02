# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Claim-lifecycle state verification for temporally-sequential claims.

``corroboration.py``'s temporal gate currently makes a binary, pairwise
call: if two NLI-contradictory claims about the same event have sequential
(non-coincident) dates, the pair is reclassified as "claim evolution" and
trusted wholesale. That's an improvement over treating any NLI disagreement
as a contradiction, but it's still weaker than it should be in two ways:

1. It's *pairwise* -- given a group with more than two dated claims, each
   pair is checked in isolation, never the sequence as a whole.
2. It's *unconditional* -- any sequential-dates disagreement is accepted as
   "evolution," even if the actual sequence of states doesn't correspond to
   any real-world process (e.g. a report of "ratified" chronologically
   *before* a report of "signed" is not legitimate evolution, it's a
   genuine inconsistency, but the pairwise gate alone can't tell the
   difference -- both cases just look like "sequential dates + NLI
   disagreement" to it).

This module adds a third layer: an explicit finite-state lifecycle model
per event type (``EVENT_LIFECYCLES``), a zero-shot classifier that maps a
claim sentence to its lifecycle state via NLI entailment (reusing the same
model as ``ContradictionDetector`` -- no second model to load), and
``verify_sequence`` to check whether a date-ordered run of claims traces a
legal path through that state machine. An illegal transition is a genuine
temporal inconsistency, not evolution, even though it would otherwise pass
the simpler pairwise gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.credibility.contradiction_nli import ContradictionDetector
from src.temporal.reasoner import _parse_date

DEFAULT_STATE_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class EventLifecycle:
    event_type: str
    transitions: dict[str, frozenset[str]]  # state -> legal next states
    state_templates: dict[str, str]  # state -> NLI hypothesis sentence

    @property
    def states(self) -> list[str]:
        return list(self.state_templates)

    @property
    def terminal_states(self) -> frozenset[str]:
        return frozenset(
            state for state, nexts in self.transitions.items() if not nexts
        )


def _lifecycle(event_type: str, transitions: dict[str, tuple[str, ...]], templates: dict[str, str]) -> EventLifecycle:
    return EventLifecycle(
        event_type=event_type,
        transitions={state: frozenset(nexts) for state, nexts in transitions.items()},
        state_templates=templates,
    )


# Hand-authored, deliberately small (3-5 states) per event type -- a first-pass
# domain ontology, not validated against real diplomatic/economic process
# literature. Each is a prototype for the framework, meant to be refined with
# domain expertise before being trusted for a real claim, same caveat as the
# EVENT_RULES trigger lexicon in event_extractor.py.
EVENT_LIFECYCLES: dict[str, EventLifecycle] = {
    "DiplomaticMeeting": _lifecycle(
        "DiplomaticMeeting",
        {
            "scheduled": ("held", "cancelled", "postponed"),
            "postponed": ("held", "cancelled", "postponed"),
            "held": (),
            "cancelled": (),
        },
        {
            "scheduled": "A meeting between the two sides was scheduled.",
            "postponed": "The meeting was postponed.",
            "held": "The meeting was held.",
            "cancelled": "The meeting was cancelled.",
        },
    ),
    "TradeAgreement": _lifecycle(
        "TradeAgreement",
        {
            "proposed": ("negotiating", "signed", "rejected"),
            "negotiating": ("signed", "rejected"),
            "signed": ("ratified", "rejected"),
            "ratified": (),
            "rejected": (),
        },
        {
            "proposed": "A trade agreement was proposed.",
            "negotiating": "Negotiations on the trade agreement are ongoing.",
            "signed": "The trade agreement was signed.",
            "ratified": "The trade agreement was ratified.",
            "rejected": "The trade agreement was rejected.",
        },
    ),
    "InvestmentProject": _lifecycle(
        "InvestmentProject",
        {
            "announced": ("under_construction", "suspended"),
            "under_construction": ("completed", "suspended"),
            "suspended": ("under_construction", "completed"),
            "completed": (),
        },
        {
            "announced": "An investment project was announced.",
            "under_construction": "The investment project is under construction.",
            "suspended": "The investment project was suspended.",
            "completed": "The investment project was completed.",
        },
    ),
    "TechnologyCooperation": _lifecycle(
        "TechnologyCooperation",
        {
            "proposed": ("agreed", "discontinued"),
            "agreed": ("implemented", "discontinued"),
            "implemented": ("discontinued",),
            "discontinued": (),
        },
        {
            "proposed": "Technology cooperation was proposed.",
            "agreed": "Both sides agreed on the technology cooperation.",
            "implemented": "The technology cooperation was implemented.",
            "discontinued": "The technology cooperation was discontinued.",
        },
    ),
    "InfrastructureProject": _lifecycle(
        "InfrastructureProject",
        {
            "planned": ("under_construction", "suspended", "cancelled"),
            "under_construction": ("completed", "suspended", "cancelled"),
            "suspended": ("under_construction", "cancelled"),
            "completed": (),
            "cancelled": (),
        },
        {
            "planned": "An infrastructure project was planned.",
            "under_construction": "The infrastructure project is under construction.",
            "suspended": "The infrastructure project was suspended.",
            "completed": "The infrastructure project was completed.",
            "cancelled": "The infrastructure project was cancelled.",
        },
    ),
    "EducationCooperation": _lifecycle(
        "EducationCooperation",
        {
            "proposed": ("established", "ended"),
            "established": ("active", "ended"),
            "active": ("ended",),
            "ended": (),
        },
        {
            "proposed": "An education cooperation program was proposed.",
            "established": "The education cooperation program was established.",
            "active": "The education cooperation program is active.",
            "ended": "The education cooperation program ended.",
        },
    ),
    "SecurityStatement": _lifecycle(
        "SecurityStatement",
        {
            "issued": ("reaffirmed", "retracted"),
            "reaffirmed": ("reaffirmed", "retracted"),
            "retracted": (),
        },
        {
            "issued": "A security statement was issued.",
            "reaffirmed": "The security statement was reaffirmed.",
            "retracted": "The security statement was retracted.",
        },
    ),
    "SanctionOrRestriction": _lifecycle(
        "SanctionOrRestriction",
        {
            "proposed": ("imposed",),
            "imposed": ("extended", "lifted"),
            "extended": ("extended", "lifted"),
            "lifted": (),
        },
        {
            "proposed": "A sanction or restriction was proposed.",
            "imposed": "The sanction or restriction was imposed.",
            "extended": "The sanction or restriction was extended.",
            "lifted": "The sanction or restriction was lifted.",
        },
    ),
    "CompanyActivity": _lifecycle(
        "CompanyActivity",
        {
            "announced": ("launched", "cancelled"),
            "launched": ("expanded", "closed"),
            "expanded": ("expanded", "closed"),
            "closed": (),
            "cancelled": (),
        },
        {
            "announced": "A company activity was announced.",
            "launched": "The company activity was launched.",
            "expanded": "The company activity was expanded.",
            "closed": "The company activity was closed.",
            "cancelled": "The company activity was cancelled.",
        },
    ),
    "CulturalExchange": _lifecycle(
        "CulturalExchange",
        {
            "planned": ("held", "cancelled", "postponed"),
            "postponed": ("held", "cancelled", "postponed"),
            "held": (),
            "cancelled": (),
        },
        {
            "planned": "A cultural exchange event was planned.",
            "postponed": "The cultural exchange event was postponed.",
            "held": "The cultural exchange event was held.",
            "cancelled": "The cultural exchange event was cancelled.",
        },
    ),
    "PolicyStatement": _lifecycle(
        "PolicyStatement",
        {
            "announced": ("reaffirmed", "revised", "retracted"),
            "reaffirmed": ("reaffirmed", "revised", "retracted"),
            "revised": ("reaffirmed", "revised", "retracted"),
            "retracted": (),
        },
        {
            "announced": "A policy statement was announced.",
            "reaffirmed": "The policy statement was reaffirmed.",
            "revised": "The policy statement was revised.",
            "retracted": "The policy statement was retracted.",
        },
    ),
}


class LifecycleStateClassifier:
    """Zero-shot claim-sentence -> lifecycle-state classifier via NLI entailment."""

    def __init__(
        self,
        detector: ContradictionDetector | None = None,
        confidence_threshold: float = DEFAULT_STATE_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._detector = detector or ContradictionDetector()
        self.confidence_threshold = confidence_threshold

    def available(self) -> bool:
        return self._detector.available()

    def classify(self, sentence: str, event_type: str) -> str | None:
        """Return the best-matching lifecycle state, or None if unclassified
        (no lifecycle defined for this event type, model unavailable, or no
        candidate state clears the confidence threshold)."""
        lifecycle = EVENT_LIFECYCLES.get(event_type)
        if not lifecycle or not self.available():
            return None
        scores = {
            state: self._detector.entailment_score(sentence, template)
            for state, template in lifecycle.state_templates.items()
        }
        best_state = max(scores, key=scores.get)
        if scores[best_state] < self.confidence_threshold:
            return None
        return best_state


@dataclass
class LifecycleViolation:
    from_state: str
    to_state: str
    from_date: str | None
    to_date: str | None
    reason: str


@dataclass
class LifecycleVerification:
    event_type: str
    state_sequence: list[tuple[str | None, str | None]]  # (state, date), date-sorted
    violations: list[LifecycleViolation] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.violations


def verify_sequence(
    event_type: str,
    dated_states: list[tuple[str | None, str | None]],  # (state, date)
) -> LifecycleVerification:
    """Check whether a date-ordered run of lifecycle states traces a legal
    path through ``EVENT_LIFECYCLES[event_type]``.

    Entries with an unclassified state (None) or unparseable date are kept
    in the output sequence for transparency but skipped as transition
    endpoints -- there's no evidence to call them a violation either way.
    Consecutive entries with the *same* state (repeated confirmation, e.g.
    two sources both reporting "signed") are never a violation regardless
    of the lifecycle's declared transitions.
    """
    lifecycle = EVENT_LIFECYCLES.get(event_type)

    def sort_key(item: tuple[str | None, str | None]):
        parsed = _parse_date(item[1])
        return (parsed is None, parsed)

    ordered = sorted(dated_states, key=sort_key)
    violations: list[LifecycleViolation] = []

    if lifecycle:
        usable = [
            (state, date) for state, date in ordered if state and _parse_date(date)
        ]
        for (prev_state, prev_date), (next_state, next_date) in zip(usable, usable[1:]):
            if prev_state == next_state:
                continue
            allowed = lifecycle.transitions.get(prev_state, frozenset())
            if next_state not in allowed:
                reason = (
                    f"'{prev_state}' has no valid transition to '{next_state}'"
                    if prev_state in lifecycle.transitions
                    else f"'{prev_state}' is not a known state for {event_type}"
                )
                violations.append(
                    LifecycleViolation(
                        from_state=prev_state,
                        to_state=next_state,
                        from_date=prev_date,
                        to_date=next_date,
                        reason=reason,
                    )
                )

    return LifecycleVerification(
        event_type=event_type, state_sequence=ordered, violations=violations
    )
