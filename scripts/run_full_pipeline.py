#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Run the end-to-end Temporal KG pipeline with tuned defaults.

This script orchestrates ingestion, extraction, credibility analysis, and optional
graph/query steps using the current Python environment.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_step(
    name: str,
    cmd: list[str],
    *,
    dry_run: bool,
    continue_on_error: bool,
) -> tuple[bool, bool]:
    printable = " ".join(shlex.quote(part) for part in cmd)
    print(f"\n[{name}]\n$ {printable}")

    if dry_run:
        return True, False

    completed = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        print(f"Step failed: {name} (exit={completed.returncode})")
        if not continue_on_error:
            return False, True
        return True, True
    return True, False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run full ingestion->extraction->credibility pipeline.",
    )
    parser.add_argument(
        "--temporal-engine",
        choices=["regex", "heideltime"],
        default="regex",
        help="Temporal extraction engine (default: regex for robustness).",
    )
    parser.add_argument(
        "--no-ingestion",
        action="store_true",
        help="Skip ingestion and use existing processed data.",
    )
    parser.add_argument(
        "--ingestion-timespan",
        metavar="SPAN",
        default=None,
        help="GDELT timespan, e.g. '24hours', '1week' (default from settings.yaml).",
    )
    parser.add_argument(
        "--ingestion-start",
        metavar="DATE",
        default=None,
        help="GDELT start date ISO format, e.g. 2024-01-01.",
    )
    parser.add_argument(
        "--ingestion-end",
        metavar="DATE",
        default=None,
        help="GDELT end date ISO format, e.g. 2024-02-01.",
    )
    parser.add_argument(
        "--ingestion-max",
        type=int,
        metavar="N",
        default=None,
        help="Max GDELT records per query, 1–250 (default from settings.yaml).",
    )
    parser.add_argument(
        "--with-deepke",
        action="store_true",
        help="Run DeepKE extraction stage before standard extraction layers.",
    )
    parser.add_argument(
        "--with-neo4j-load",
        action="store_true",
        help="Load extracted outputs into Neo4j after local pipeline steps.",
    )
    parser.add_argument(
        "--with-competency-queries",
        action="store_true",
        help="Run competency queries and write report JSON.",
    )
    parser.add_argument(
        "--competency-output",
        type=Path,
        default=Path("data/exports/reports/competency_queries.json"),
        help="Output JSON path for competency queries.",
    )
    parser.add_argument(
        "--credibility-threshold",
        type=float,
        default=0.3,
        help="General low-credibility reporting threshold.",
    )
    parser.add_argument(
        "--fake-news-threshold",
        type=float,
        default=0.9,
        help="Threshold for labeling unverified claims as fake_news.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining steps even if one step fails.",
    )
    parser.add_argument(
        "--fallback-temporal-engine",
        choices=["regex", "heideltime", "none"],
        default="regex",
        help="Fallback temporal engine if primary temporal extraction fails.",
    )
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit non-zero if any step fails, even with --continue-on-error.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    args = parser.parse_args()

    py = sys.executable
    steps: list[tuple[str, list[str]]] = []

    steps.append(("init_project", [py, "scripts/init_project.py"]))

    if not args.no_ingestion:
        ingestion_cmd = [py, "scripts/run_ingestion.py"]
        if args.ingestion_timespan:
            ingestion_cmd.extend(["--timespan", args.ingestion_timespan])
        if args.ingestion_start:
            ingestion_cmd.extend(["--start", args.ingestion_start])
        if args.ingestion_end:
            ingestion_cmd.extend(["--end", args.ingestion_end])
        if args.ingestion_max is not None:
            ingestion_cmd.extend(["--max", str(args.ingestion_max)])
        steps.append(("ingestion", ingestion_cmd))

    steps.extend(
        [
            ("entity_extraction", [py, "scripts/run_entity_extraction.py"]),
            (
                "temporal_extraction",
                [
                    py,
                    "scripts/run_temporal_extraction.py",
                    "--engine",
                    args.temporal_engine,
                ],
            ),
            ("event_extraction", [py, "scripts/run_event_extraction.py"]),
            ("relation_extraction", [py, "scripts/run_relation_extraction.py"]),
            (
                "corroboration_analysis",
                [py, "scripts/run_corroboration_analysis.py"],
            ),
            (
                "claim_assessment",
                [py, "scripts/run_fake_news_analysis.py"],
            ),
            (
                "export_contradictions_fake_news",
                [
                    py,
                    "scripts/export_contradictions_fake_news.py",
                    "--credibility-threshold",
                    str(args.credibility_threshold),
                    "--fake-news-threshold",
                    str(args.fake_news_threshold),
                ],
            ),
        ]
    )

    if args.with_deepke:
        steps.insert(
            2 if not args.no_ingestion else 1,
            ("deepke_extraction", [py, "scripts/run_deepke_extraction.py"]),
        )

    if args.with_neo4j_load:
        steps.append(("neo4j_load", [py, "scripts/load_graph.py"]))

    if args.with_competency_queries:
        steps.append(
            (
                "competency_queries",
                [
                    py,
                    "scripts/run_competency_queries.py",
                    "--query",
                    "all",
                    "--format",
                    "json",
                    "--output",
                    str(args.competency_output),
                ],
            )
        )

    print("Running full pipeline with settings:")
    print(f"  temporal_engine={args.temporal_engine}")
    print(f"  credibility_threshold={args.credibility_threshold}")
    print(f"  fake_news_threshold={args.fake_news_threshold}")
    print(f"  with_neo4j_load={args.with_neo4j_load}")
    print(f"  with_competency_queries={args.with_competency_queries}")
    print(f"  with_deepke={args.with_deepke}")
    print(f"  continue_on_error={args.continue_on_error}")
    print(f"  fallback_temporal_engine={args.fallback_temporal_engine}")
    print(f"  strict_exit={args.strict_exit}")
    if args.no_ingestion:
        print("  ingestion=SKIPPED")
    else:
        gdelt_range = args.ingestion_timespan or (
            f"{args.ingestion_start or '?'} → {args.ingestion_end or '?'}"
        )
        print(f"  ingestion=GDELT  range={gdelt_range}  max={args.ingestion_max or 'default'}")

    started = time.time()
    failed_steps: list[str] = []

    for name, cmd in steps:
        ok, failed = _run_step(
            name,
            cmd,
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
        )

        if (
            name == "temporal_extraction"
            and failed
            and args.temporal_engine != args.fallback_temporal_engine
            and args.fallback_temporal_engine != "none"
        ):
            fallback_cmd = [
                py,
                "scripts/run_temporal_extraction.py",
                "--engine",
                args.fallback_temporal_engine,
            ]
            print(
                "Primary temporal extraction failed; retrying with fallback "
                f"engine={args.fallback_temporal_engine}."
            )
            fallback_ok, fallback_failed = _run_step(
                f"temporal_extraction_fallback_{args.fallback_temporal_engine}",
                fallback_cmd,
                dry_run=args.dry_run,
                continue_on_error=args.continue_on_error,
            )
            if not fallback_failed:
                failed = False
                ok = True
            else:
                failed_steps.append(
                    f"temporal_extraction_fallback_{args.fallback_temporal_engine}"
                )
                ok = fallback_ok

        if failed:
            failed_steps.append(name)
        if not ok:
            break

    elapsed = time.time() - started
    print("\n" + "=" * 70)
    if failed_steps:
        print(f"Pipeline finished with failures in {len(failed_steps)} step(s):")
        for step_name in failed_steps:
            print(f"  - {step_name}")
        print(f"Elapsed: {elapsed:.1f}s")
        if args.continue_on_error and not args.strict_exit:
            print("Returning success exit code due to --continue-on-error.")
            sys.exit(0)
        sys.exit(1)

    print("Pipeline completed successfully.")
    print(f"Elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
