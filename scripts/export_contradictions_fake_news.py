#!/usr/bin/env python3
"""Export contradictions and likely fake-news claims, then print the last 3."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.fake_news import ClaimAssessment, ClaimVerifier  # noqa: E402
from src.utils.config import settings  # noqa: E402


def _is_fake_news_candidate(
    assessment: ClaimAssessment, fake_news_threshold: float
) -> bool:
    has_conflict = assessment.contradiction_flag or bool(assessment.temporal_issues)
    status = assessment.verification_status
    low_for_fake_news = assessment.credibility_score < fake_news_threshold

    # Conservative rule:
    # - any conflict or contested claim is fake_news candidate,
    # - unverified claims are fake_news candidates only if score is below
    #   a dedicated, higher fake-news threshold.
    return bool(
        has_conflict
        or status == "contested"
        or (status == "unverified" and low_for_fake_news)
    )


def _labels(
    assessment: ClaimAssessment,
    threshold: float,
    fake_news_threshold: float,
) -> list[str]:
    labels: list[str] = []
    if assessment.contradiction_flag or assessment.temporal_issues:
        labels.append("contradiction")
    if _is_fake_news_candidate(assessment, fake_news_threshold):
        labels.append("fake_news")
    return labels


def _reasons(
    assessment: ClaimAssessment,
    threshold: float,
    fake_news_threshold: float,
) -> list[str]:
    reasons: list[str] = []
    if assessment.contradiction_flag:
        reasons.append("contradiction")
    if assessment.temporal_issues:
        reasons.append("temporal_inconsistency")
    if assessment.verification_status in {"contested", "unverified"}:
        reasons.append(f"status:{assessment.verification_status}")
    if assessment.credibility_score < threshold:
        reasons.append(f"low_credibility:<{threshold}")
    if assessment.credibility_score < fake_news_threshold:
        reasons.append(f"fake_news_score:<{fake_news_threshold}")
    return reasons


def _is_suspicious(
    assessment: ClaimAssessment,
    threshold: float,
    fake_news_threshold: float,
) -> bool:
    return bool(_labels(assessment, threshold, fake_news_threshold))


def _build_row(
    assessment: ClaimAssessment,
    threshold: float,
    fake_news_threshold: float,
) -> dict:
    row = asdict(assessment)
    row["labels"] = _labels(assessment, threshold, fake_news_threshold)
    row["reasons"] = _reasons(assessment, threshold, fake_news_threshold)
    return row


def _bucket(row: dict) -> str:
    labels = set(row.get("labels", []))
    if {"contradiction", "fake_news"}.issubset(labels):
        return "both"
    if "contradiction" in labels:
        return "just_contradiction"
    if "fake_news" in labels:
        return "just_fake_news"
    return "unclassified"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export contradictions/fake-news candidates and print the last 3."
    )
    parser.add_argument(
        "--entities-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "entities",
    )
    parser.add_argument(
        "--temporals-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "temporals",
    )
    parser.add_argument(
        "--events-dir",
        type=Path,
        default=settings.abs_path("paths.data_exports") / "events",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=settings.abs_path("paths.data_exports")
        / "credibility"
        / "contradictions_fake_news.json",
    )
    parser.add_argument(
        "--credibility-threshold",
        type=float,
        default=0.3,
        help="General low-credibility threshold used for reporting reasons.",
    )
    parser.add_argument(
        "--fake-news-threshold",
        type=float,
        default=0.9,
        help=(
            "Dedicated score threshold for labeling unverified claims as fake_news. "
            "Higher means more sensitive."
        ),
    )
    args = parser.parse_args()

    verifier = ClaimVerifier()
    assessments = verifier.assess(
        entities_dir=args.entities_dir,
        temporals_dir=args.temporals_dir,
        events_dir=args.events_dir,
    )

    flagged = [
        _build_row(item, args.credibility_threshold, args.fake_news_threshold)
        for item in assessments
        if _is_suspicious(
            item,
            args.credibility_threshold,
            args.fake_news_threshold,
        )
    ]

    both = [row for row in flagged if _bucket(row) == "both"]
    just_contradiction = [
        row for row in flagged if _bucket(row) == "just_contradiction"
    ]
    just_fake_news = [row for row in flagged if _bucket(row) == "just_fake_news"]

    contradictions = both + just_contradiction
    fake_news = both + just_fake_news

    payload = {
        "summary": {
            "total_assessed": len(assessments),
            "flagged_total": len(flagged),
            "contradictions": len(contradictions),
            "fake_news": len(fake_news),
            "both": len(both),
            "just_contradiction": len(just_contradiction),
            "just_fake_news": len(just_fake_news),
        },
        "both": both,
        "just_contradiction": just_contradiction,
        "just_fake_news": just_fake_news,
        "contradictions": contradictions,
        "fake_news": fake_news,
    }

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote categorized claims to {args.output_path}")
    print(f"Summary: {payload['summary']}")

    print("\nLast 3 both:")
    for row in both[-3:]:
        print(json.dumps(row, ensure_ascii=False, indent=2))

    print("\nLast 3 just_contradiction:")
    for row in just_contradiction[-3:]:
        print(json.dumps(row, ensure_ascii=False, indent=2))

    print("\nLast 3 just_fake_news:")
    for row in just_fake_news[-3:]:
        print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
