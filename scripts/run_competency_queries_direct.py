#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Compute the five competency questions (CQ1-CQ5) directly against the JSON
exports, without requiring a running Neo4j instance.

``src/graph/competency_queries.py`` implements these as Cypher queries against
the populated graph; that requires Neo4j to be installed and running, which
this project has deliberately avoided setting up (see CLAUDE.md -- "don't
make the setup complicated"). Since the graph is itself loaded from the same
``data/exports/{entities,events,temporals}`` JSON this script reads, the
query *logic* -- event-type filtering, the china+romania bilateral gate, and
date-range filtering -- is reproducible directly against the JSON without the
graph layer in between. Reuses
``KnowledgeGraphLoader._temporal_record`` for date resolution so this stays
consistent with the actual pipeline's date-handling logic rather than
reimplementing it.

One deliberate simplification vs. the Cypher queries: those check that China
and Romania entities are ``INVOLVES`` participants of the *specific event*
(a narrower, per-event graph traversal). This script instead gates on
article-level China+Romania co-occurrence (already guaranteed by
RelevanceFilter for every article in the corpus) combined with event-type and
date filtering -- a coarser but still faithful reproduction of "bilateral
events about X", not a byte-identical query. This is why CQ2 in particular
(which specifically needs event-level entity-pair linkage, not just
article-level co-occurrence) is reported with that caveat below.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.pipeline_utils import load_json_by_article  # noqa: E402
from src.graph.graph_loader import KnowledgeGraphLoader  # noqa: E402
from src.utils.config import settings  # noqa: E402

ECONOMIC_TYPES = {"TradeAgreement", "InvestmentProject", "CompanyActivity", "InfrastructureProject"}
CATEGORY_MAP = {
    "trade": {"TradeAgreement", "InvestmentProject", "CompanyActivity"},
    "diplomatic": {"DiplomaticMeeting", "PolicyStatement"},
    "cultural": {"CulturalExchange", "EducationCooperation"},
    "policy": {"PolicyStatement", "SecurityStatement", "SanctionOrRestriction"},
    "infrastructure": {"InfrastructureProject"},
    "technology": {"TechnologyCooperation"},
}
RESEARCH_TYPES = {"TechnologyCooperation", "EducationCooperation"}


def _load_corpus() -> tuple[dict, dict, dict]:
    entities_dir = settings.abs_path("paths.data_exports") / "entities"
    temporals_dir = settings.abs_path("paths.data_exports") / "temporals"
    events_dir = settings.abs_path("paths.data_exports") / "events"
    return (
        load_json_by_article(entities_dir),
        load_json_by_article(temporals_dir),
        load_json_by_article(events_dir),
    )


def _is_bilateral_article(entity_payload: dict) -> bool:
    names = [
        (e.get("canonical_name") or "").lower()
        for e in entity_payload.get("entities", [])
    ]
    return any("china" in n for n in names) and any("romania" in n for n in names)


def _resolve_dates(temporal_payload: dict, article_id: str) -> dict[str, dict]:
    out = {}
    for item in temporal_payload.get("temporal_expressions", []):
        out[item["temporal_id"]] = KnowledgeGraphLoader._temporal_record(item, article_id)
    return out


def _iter_bilateral_events(entity_payloads, temporal_payloads, event_payloads):
    """Yield (article_id, source_article, event, date) for every event in a
    bilateral (China+Romania co-mentioning) article."""
    for article_id, event_payload in sorted(event_payloads.items()):
        entity_payload = entity_payloads.get(article_id, {})
        if not _is_bilateral_article(entity_payload):
            continue
        source_article = event_payload.get("source_article", {})
        temporal_map = _resolve_dates(temporal_payloads.get(article_id, {}), article_id)
        for event in event_payload.get("events", []):
            temporal = temporal_map.get(event.get("temporal_id"))
            date = (
                (temporal.get("start_date") or temporal.get("end_date"))
                if temporal
                else None
            ) or source_article.get("published_at")
            yield article_id, source_article, event, date


def cq1_economic_evolution(entity_payloads, temporal_payloads, event_payloads,
                            start_date="2020-01-01", end_date="2026-12-31"):
    breakdown = Counter()
    key_entities = Counter()
    total = 0
    for article_id, source_article, event, date in _iter_bilateral_events(
        entity_payloads, temporal_payloads, event_payloads
    ):
        if event["event_type"] not in ECONOMIC_TYPES:
            continue
        d = (date or "")[:10]
        if not (start_date <= d <= end_date):
            continue
        total += 1
        breakdown[event["event_type"]] += 1
        for eid in event.get("participant_entity_ids", []):
            for e in entity_payloads.get(article_id, {}).get("entities", []):
                if e["entity_id"] == eid and e.get("entity_type") in ("ORGANIZATION", "ORG"):
                    key_entities[e.get("canonical_name")] += 1
    return {
        "total_events": total,
        "event_breakdown": dict(breakdown.most_common()),
        "key_entities": key_entities.most_common(20),
        "period": f"{start_date} to {end_date}",
    }


def cq2_romanian_institutions_chinese_companies(entity_payloads, event_payloads):
    """Caveat: this is the one CQ where the article-level bilateral gate is a
    real simplification of the Cypher's event-participant-level join -- see
    module docstring. Reported honestly as such."""
    pairs: dict[str, set[str]] = defaultdict(set)
    for article_id, event_payload in sorted(event_payloads.items()):
        entities = entity_payloads.get(article_id, {}).get("entities", [])
        romanian_orgs = [
            e for e in entities
            if e.get("entity_type") in ("ORGANIZATION", "ORG")
            and "romania" in (e.get("canonical_name") or "").lower()
        ]
        chinese_orgs = [
            e for e in entities
            if e.get("entity_type") in ("ORGANIZATION", "ORG")
            and "china" in (e.get("canonical_name") or "").lower()
        ]
        for r in romanian_orgs:
            for c in chinese_orgs:
                pairs[r["canonical_name"]].add(c["canonical_name"])
    return {name: sorted(companies) for name, companies in pairs.items()}


def cq3_bilateral_events_in_period(entity_payloads, temporal_payloads, event_payloads,
                                    start_date, end_date):
    by_type = Counter()
    total = 0
    for article_id, source_article, event, date in _iter_bilateral_events(
        entity_payloads, temporal_payloads, event_payloads
    ):
        all_types = set()
        for types in CATEGORY_MAP.values():
            all_types |= types
        if event["event_type"] not in all_types:
            continue
        d = (date or "")[:10]
        if not (start_date <= d <= end_date):
            continue
        total += 1
        by_type[event["event_type"]] += 1
    return {"period": f"{start_date} to {end_date}", "total_events": total,
            "event_type_counts": dict(by_type.most_common())}


def cq4_contradicted_or_unverified(claims_path: Path):
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    status_counts = Counter(c["verification_status"] for c in claims)
    return {"total_claims": len(claims), "status_counts": dict(status_counts)}


def cq5_collaborative_research(entity_payloads, temporal_payloads, event_payloads):
    results = []
    for article_id, source_article, event, date in _iter_bilateral_events(
        entity_payloads, temporal_payloads, event_payloads
    ):
        if event["event_type"] not in RESEARCH_TYPES:
            continue
        results.append({
            "event_type": event["event_type"],
            "sentence": event.get("sentence", "")[:150],
            "date": date,
            "article_title": source_article.get("title"),
            "source": source_article.get("source_name"),
        })
    return results


def main() -> None:
    entity_payloads, temporal_payloads, event_payloads = _load_corpus()
    claims_path = settings.abs_path("paths.data_exports") / "credibility" / "corroboration.claims.json"

    print(f"Loaded {len(event_payloads)} bilateral-corpus articles.\n")

    print("=== CQ1: Economic evolution 2020-2026 ===")
    cq1 = cq1_economic_evolution(entity_payloads, temporal_payloads, event_payloads)
    print(json.dumps(cq1, ensure_ascii=False, indent=2))

    print("\n=== CQ2: Romanian institutions <-> Chinese companies (article-level co-occurrence, see caveat) ===")
    cq2 = cq2_romanian_institutions_chinese_companies(entity_payloads, event_payloads)
    print(f"{len(cq2)} Romanian institution(s) with co-occurring Chinese company mentions")
    for k, v in list(cq2.items())[:10]:
        print(f"  {k}: {v}")

    print("\n=== CQ3: Bilateral events, full corpus date range ===")
    all_dates = [
        (temporal_payloads.get(aid, {}) and None) for aid in event_payloads
    ]
    cq3 = cq3_bilateral_events_in_period(
        entity_payloads, temporal_payloads, event_payloads,
        start_date="2000-01-01", end_date="2030-01-01",
    )
    print(json.dumps(cq3, ensure_ascii=False, indent=2))

    print("\n=== CQ4: Contradicted/unverified claims ===")
    cq4 = cq4_contradicted_or_unverified(claims_path)
    print(json.dumps(cq4, ensure_ascii=False, indent=2))

    print("\n=== CQ5: Collaborative research events ===")
    cq5 = cq5_collaborative_research(entity_payloads, temporal_payloads, event_payloads)
    print(f"{len(cq5)} collaborative-research event(s)")
    for r in cq5[:10]:
        print(f"  [{r['date']}] {r['event_type']}: {r['sentence']}")

    out = {"cq1": cq1, "cq2_institution_count": len(cq2), "cq2_pairs": cq2,
           "cq3": cq3, "cq4": cq4, "cq5": cq5}
    out_path = settings.abs_path("paths.data_exports") / "competency_queries_direct.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote full results to {out_path}")


if __name__ == "__main__":
    main()
