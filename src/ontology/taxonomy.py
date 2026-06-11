# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Ontology mappings for bilateral event types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventTaxonomy:
    event_type: str
    cameo_category: str
    gdelt_category: str
    iptc_topic: str
    description: str


EVENT_TAXONOMY: dict[str, EventTaxonomy] = {
    "DiplomaticMeeting": EventTaxonomy(
        event_type="DiplomaticMeeting",
        cameo_category="04 Consult",
        gdelt_category="Diplomatic Cooperation",
        iptc_topic="Politics/Diplomacy",
        description="Official diplomatic meetings and talks.",
    ),
    "TradeAgreement": EventTaxonomy(
        event_type="TradeAgreement",
        cameo_category="07 Provide Aid",
        gdelt_category="Economic Cooperation",
        iptc_topic="Economy, Business and Finance/Trade",
        description="Trade agreements, MOUs, and commercial deals.",
    ),
    "InvestmentProject": EventTaxonomy(
        event_type="InvestmentProject",
        cameo_category="08 Yield",
        gdelt_category="Economic Investment",
        iptc_topic="Economy, Business and Finance/Investment",
        description="Infrastructure and investment projects.",
    ),
    "TechnologyCooperation": EventTaxonomy(
        event_type="TechnologyCooperation",
        cameo_category="05 Engage in Diplomatic Cooperation",
        gdelt_category="Science and Technology",
        iptc_topic="Science and Technology/Research",
        description="Joint technology, research, or innovation initiatives.",
    ),
    "InfrastructureProject": EventTaxonomy(
        event_type="InfrastructureProject",
        cameo_category="07 Provide Aid",
        gdelt_category="Infrastructure",
        iptc_topic="Economy, Business and Finance/Construction",
        description="Transport, energy, and major infrastructure works.",
    ),
    "EducationCooperation": EventTaxonomy(
        event_type="EducationCooperation",
        cameo_category="05 Engage in Diplomatic Cooperation",
        gdelt_category="Education",
        iptc_topic="Education",
        description="Academic cooperation, scholarships, exchanges.",
    ),
    "SecurityStatement": EventTaxonomy(
        event_type="SecurityStatement",
        cameo_category="13 Threaten",
        gdelt_category="Security",
        iptc_topic="Crime, Law and Justice/Defence",
        description="Security statements, defense policy remarks.",
    ),
    "SanctionOrRestriction": EventTaxonomy(
        event_type="SanctionOrRestriction",
        cameo_category="11 Sanctions",
        gdelt_category="Sanctions",
        iptc_topic="Politics/Sanctions",
        description="Sanctions, restrictions, export controls.",
    ),
    "CompanyActivity": EventTaxonomy(
        event_type="CompanyActivity",
        cameo_category="07 Provide Aid",
        gdelt_category="Corporate Activity",
        iptc_topic="Economy, Business and Finance/Companies",
        description="Company operations, investments, or expansions.",
    ),
    "CulturalExchange": EventTaxonomy(
        event_type="CulturalExchange",
        cameo_category="05 Engage in Diplomatic Cooperation",
        gdelt_category="Cultural Exchange",
        iptc_topic="Arts, Culture and Entertainment",
        description="Cultural programs, festivals, exhibitions.",
    ),
    "PolicyStatement": EventTaxonomy(
        event_type="PolicyStatement",
        cameo_category="01 Public Statement",
        gdelt_category="Policy",
        iptc_topic="Politics",
        description="Official policy statements and announcements.",
    ),
}


def annotate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Attach taxonomy metadata to an event record."""
    taxonomy = EVENT_TAXONOMY.get(event.get("event_type"))
    if not taxonomy:
        return event
    event["taxonomy"] = {
        "cameo_category": taxonomy.cameo_category,
        "gdelt_category": taxonomy.gdelt_category,
        "iptc_topic": taxonomy.iptc_topic,
        "description": taxonomy.description,
    }
    return event
