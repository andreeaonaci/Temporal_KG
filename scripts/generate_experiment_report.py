#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Turn a pipeline run's raw JSON exports into a paper-ready summary report.

Every real-data check so far in this project happened by eyeballing raw
JSON by hand (pasting claim_assessments.json into chat, scanning for
non-default values). That doesn't scale past one run, and it's exactly the
kind of manual step that's easy to get subtly wrong (miscounting, missing a
record) when repeated across every future ingestion/extraction cycle. This
script computes the same aggregate statistics a paper's results section
would report -- verification-status distribution, corroboration/diversity
rates, contradiction/evolution/lifecycle-violation counts, credibility-tier
breakdown -- directly from corroboration.claims.json and
claim_assessments.json, plus flags the specific groups worth a manual read
(contested, lifecycle violations, highest support_count) instead of making
you scroll through everything to find them.

Usage:
    python scripts/generate_experiment_report.py
    python scripts/generate_experiment_report.py \\
        --claims data/exports/credibility/corroboration.claims.json \\
        --assessments data/exports/credibility/claim_assessments.json \\
        --out data/exports/experiment_report.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CLAIMS = PROJECT_ROOT / "data" / "exports" / "credibility" / "corroboration.claims.json"
DEFAULT_ASSESSMENTS = PROJECT_ROOT / "data" / "exports" / "credibility" / "claim_assessments.json"
DEFAULT_OUT = PROJECT_ROOT / "data" / "exports" / "experiment_report.md"

FLAG_FIELDS = (
    "contradiction_flag",
    "structural_contradiction_flag",
    "semantic_contradiction_flag",
    "claim_evolution_flag",
    "lifecycle_violation_flag",
)


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"WARNING: {path} does not exist -- skipping that section.")
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.1f}%" if total else "n/a"


def _credibility_tier(score: float) -> str:
    if score >= 0.99:
        return "reliable (1.0)"
    if 0.6 <= score < 0.99:
        return "state-affiliated / partial (0.6-0.99)"
    if score == 0.5:
        return "default / unknown source (0.5)"
    return "other"


def build_report(claims: list[dict[str, Any]], assessments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Experiment Report")
    lines.append("")

    total = len(claims)
    lines.append(f"## Corroboration summary ({total} claim groups)")
    lines.append("")

    if total:
        status_counts = Counter(c["verification_status"] for c in claims)
        lines.append("**Verification status distribution:**")
        lines.append("")
        lines.append("| Status | Count | % |")
        lines.append("|---|---|---|")
        for status, count in status_counts.most_common():
            lines.append(f"| {status} | {count} | {_pct(count, total)} |")
        lines.append("")

        support_counts = Counter(c["support_count"] for c in claims)
        lines.append("**Support count distribution (articles per claim group):**")
        lines.append("")
        lines.append("| Support count | Groups | % |")
        lines.append("|---|---|---|")
        for support, count in sorted(support_counts.items()):
            lines.append(f"| {support} | {count} | {_pct(count, total)} |")
        lines.append("")

        real_corroboration = sum(1 for c in claims if c["source_diversity"] >= 2)
        lines.append(
            f"**Real cross-outlet corroboration** (source_diversity >= 2): "
            f"{real_corroboration}/{total} ({_pct(real_corroboration, total)})"
        )
        lines.append("")

        lines.append("**Flag counts:**")
        lines.append("")
        lines.append("| Flag | Count | % |")
        lines.append("|---|---|---|")
        for field in FLAG_FIELDS:
            n = sum(1 for c in claims if c.get(field))
            lines.append(f"| {field} | {n} | {_pct(n, total)} |")
        lines.append("")

        credibility_scores = [c["credibility_score"] for c in claims]
        tier_counts = Counter(_credibility_tier(s) for s in credibility_scores)
        lines.append("**Credibility score tiers:**")
        lines.append("")
        lines.append("| Tier | Count | % |")
        lines.append("|---|---|---|")
        for tier, count in tier_counts.most_common():
            lines.append(f"| {tier} | {count} | {_pct(count, total)} |")
        lines.append("")
        lines.append(
            f"Mean credibility: {statistics.mean(credibility_scores):.3f}  |  "
            f"Median: {statistics.median(credibility_scores):.3f}"
        )
        lines.append("")

        event_type_counts = Counter(t for c in claims for t in c.get("event_types", []))
        lines.append("**Event types represented:**")
        lines.append("")
        lines.append("| Event type | Count |")
        lines.append("|---|---|")
        for etype, count in event_type_counts.most_common():
            lines.append(f"| {etype} | {count} |")
        lines.append("")

    if assessments:
        veracity_scores = [a["veracity_score"] for a in assessments if a.get("veracity_score") is not None]
        if veracity_scores:
            lines.append(f"## Veracity summary ({len(assessments)} assessments)")
            lines.append("")
            lines.append(
                f"Mean veracity score: {statistics.mean(veracity_scores):.3f}  |  "
                f"Median: {statistics.median(veracity_scores):.3f}  |  "
                f"Std dev: {statistics.pstdev(veracity_scores):.3f}"
            )
            lines.append("")

    lines.append("## Groups worth a manual read")
    lines.append("")

    contested = [c for c in claims if c.get("contradiction_flag")]
    if contested:
        lines.append(f"**Contested/contradictory ({len(contested)}):**")
        lines.append("")
        for c in contested:
            lines.append(
                f"- `{c['record_key']}` -- support={c['support_count']}, "
                f"diversity={c['source_diversity']}, domains={c.get('source_domains')}"
            )
            lines.append(f"  - {c['sample_sentence'][:160]}")
        lines.append("")

    lifecycle_violations = [c for c in claims if c.get("lifecycle_violation_flag")]
    if lifecycle_violations:
        lines.append(f"**Lifecycle violations ({len(lifecycle_violations)}):**")
        lines.append("")
        for c in lifecycle_violations:
            lines.append(f"- `{c['record_key']}` -- {c['sample_sentence'][:160]}")
        lines.append("")

    top_support = sorted(claims, key=lambda c: c["support_count"], reverse=True)[:5]
    if top_support:
        lines.append("**Highest support_count groups (most corroborated real claims):**")
        lines.append("")
        for c in top_support:
            lines.append(
                f"- `{c['record_key']}` -- support={c['support_count']}, "
                f"diversity={c['source_diversity']}, status={c['verification_status']}"
            )
        lines.append("")

    if not (contested or lifecycle_violations):
        lines.append("Nothing flagged this run -- no contested or lifecycle-violation groups.")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a paper-ready summary from pipeline JSON exports.")
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--assessments", type=Path, default=DEFAULT_ASSESSMENTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    claims = _load(args.claims)
    assessments = _load(args.assessments)
    report = build_report(claims, assessments)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    try:
        print(report)
    except UnicodeEncodeError:
        # Windows consoles often default to a codepage (e.g. cp1250) that
        # can't display CJK characters -- real content here now that GDELT
        # historical backfill pulls in Chinese-language sources. The report
        # file itself is already written as UTF-8 above and is unaffected;
        # this only degrades what's echoed to the terminal.
        print(
            report.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8", errors="replace"
            )
        )
    print(f"\nWrote report to {args.out}")


if __name__ == "__main__":
    main()
