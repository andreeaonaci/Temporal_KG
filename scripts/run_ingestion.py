#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
scripts/run_ingestion.py
~~~~~~~~~~~~~~~~~~~~~~~~~
CLI entry point — runs the GDELT ingestion pipeline.

Usage
-----
    # Run with default settings (last 1 week):
    python scripts/run_ingestion.py

    # Custom timespan:
    python scripts/run_ingestion.py --timespan 24hours

    # Explicit date range:
    python scripts/run_ingestion.py --start 2024-01-01 --end 2024-02-01

    # Custom record cap:
    python scripts/run_ingestion.py --max 100

    # Dry-run: query GDELT but skip download + DB writes:
    python scripts/run_ingestion.py --dry-run

    # Show only relevant articles summary:
    python scripts/run_ingestion.py --relevant-only
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ── Add project root to path ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.models import IngestionRunStats
from src.ingestion.relevance_filter import RelevanceFilter
from src.utils.db import get_db
from src.utils.logger import get_logger

log = get_logger("run_ingestion")


def ensure_db_ready() -> None:
    """Run pending migrations before the pipeline starts."""
    migrations_dir = PROJECT_ROOT / "db" / "migrations"
    with get_db() as db:
        db.run_migrations(migrations_dir)


def print_run_summary(all_stats: list[IngestionRunStats], relevant_only: bool) -> None:
    """Pretty-print a summary table of all feed runs."""
    total_new = sum(s.articles_new for s in all_stats)
    total_dup = sum(s.articles_dup for s in all_stats)
    total_rel = sum(s.articles_relevant for s in all_stats)
    total_err = sum(s.errors for s in all_stats)

    print("\n" + "═" * 72)
    print(f"  Ingestion complete — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 72)

    if not relevant_only:
        print(f"  {'Feed':<35} {'New':>5} {'Dup':>5} {'Rel':>5} {'Err':>5} {'s':>6}")
        print("  " + "─" * 68)
        for s in all_stats:
            name = s.feed_name[:34]
            dur = f"{s.duration_seconds:.0f}" if s.duration_seconds else "?"
            marker = " ✓" if s.status == "success" else " ✗"
            print(f"  {name:<35} {s.articles_new:>5} {s.articles_dup:>5} "
                  f"{s.articles_relevant:>5} {s.errors:>5} {dur:>6}{marker}")
        print("  " + "─" * 68)

    print(
        f"  TOTAL: {total_new} new  |  {total_dup} duplicates  |"
        f"  {total_rel} relevant  |  {total_err} errors"
    )
    print("═" * 72 + "\n")


def show_relevant_sample(limit: int = 10) -> None:
    """Print a sample of relevant articles with both China and Romania matches."""
    matcher = RelevanceFilter()
    try:
        with get_db() as db:
            rows = db.fetchall(
                """
                SELECT title, url, published_at, language, relevance_reason, content_clean
                FROM   articles
                WHERE  is_relevant = 1
                ORDER  BY fetched_at DESC
                LIMIT  ?
                """,
                (max(limit * 5, limit),),
            )
    except Exception as exc:
        log.error("Could not query relevant articles: %s", exc)
        return

    shown = 0
    print(f"\n  Latest relevant article(s) with both China + Romania matches:")
    print("  " + "─" * 68)
    for row in rows:
        title = textwrap.shorten(row.get("title") or "(no title)", width=65)
        pub = (row.get("published_at") or "")[:10]
        lang = row.get("language") or "?"
        corpus = f"{row.get('title') or ''}\n{row.get('content_clean') or ''}"
        china_hits, romania_hits = matcher.extract_matches(corpus)
        if not china_hits or not romania_hits:
            continue

        print(f"  [{pub}] ({lang}) {title}")
        print(f"         {row['url']}")
        print(f"         matched_china: {', '.join(china_hits) if china_hits else '-'}")
        print(f"         matched_romania: {', '.join(romania_hits) if romania_hits else '-'}")
        shown += 1
        if shown >= limit:
            break

    if shown == 0:
        print("  No dual-match relevant articles found yet.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the temporal_kg GDELT ingestion pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python scripts/run_ingestion.py
              python scripts/run_ingestion.py --timespan 24hours
              python scripts/run_ingestion.py --start 2024-01-01 --end 2024-02-01
              python scripts/run_ingestion.py --max 100 --dry-run
            """
        ),
    )

    parser.add_argument(
        "--timespan",
        metavar="SPAN",
        default=None,
        help=(
            "GDELT timespan token, e.g. '24hours', '1week', '1month'. "
            "Mutually exclusive with --start/--end. "
            "Defaults to the value in settings.yaml (gdelt.default_timespan)."
        ),
    )
    parser.add_argument(
        "--start",
        metavar="DATE",
        default=None,
        help="Start date for GDELT query (ISO format, e.g. 2024-01-01).",
    )
    parser.add_argument(
        "--end",
        metavar="DATE",
        default=None,
        help="End date for GDELT query (ISO format, e.g. 2024-02-01).",
    )
    parser.add_argument(
        "--max",
        type=int,
        metavar="N",
        default=None,
        help="Max GDELT records per query (1–250, default from settings.yaml).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Query GDELT only; no downloads or DB writes.")
    parser.add_argument("--no-progress", action="store_true", help="Suppress progress bars.")
    parser.add_argument("--relevant-only", action="store_true", help="Show only relevant-articles summary.")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("temporal_kg GDELT ingestion pipeline starting")
    log.info("=" * 60)

    start_date: datetime | None = None
    end_date: datetime | None = None

    if args.start:
        try:
            start_date = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        except ValueError:
            log.error("Invalid --start date '%s'. Use ISO format YYYY-MM-DD.", args.start)
            sys.exit(1)

    if args.end:
        try:
            end_date = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        except ValueError:
            log.error("Invalid --end date '%s'. Use ISO format YYYY-MM-DD.", args.end)
            sys.exit(1)

    if args.dry_run:
        log.info("DRY RUN — querying GDELT API only, no downloads or DB writes.")
        from src.ingestion.gdelt_fetcher import GdeltFetcher
        fetcher = GdeltFetcher()
        stubs = fetcher.fetch(
            start_date=start_date,
            end_date=end_date,
            timespan=args.timespan or None,
            max_records=args.max,
        )
        log.info("GDELT dry-run: %d stubs found", len(stubs))
        for s in stubs[:10]:
            log.info("  [%s] %s  (%s)", s.published_at, s.title[:80], s.url[:60])
        return

    if not args.dry_run:
        ensure_db_ready()

    from src.ingestion.gdelt_pipeline import GdeltIngestionPipeline

    pipeline = GdeltIngestionPipeline(show_progress=not args.no_progress)
    stats = pipeline.run(
        start_date=start_date,
        end_date=end_date,
        timespan=args.timespan or None,
        max_records=args.max,
    )
    all_stats = [stats]

    print_run_summary(all_stats, relevant_only=args.relevant_only)
    show_relevant_sample()


if __name__ == "__main__":
    main()

