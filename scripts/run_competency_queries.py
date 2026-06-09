#!/usr/bin/env python3
"""Run competency queries from requirements paper on the temporal knowledge graph.

This script executes the competency questions outlined in the requirements paper
and generates a report with the results.

Usage:
    python scripts/run_competency_queries.py
    python scripts/run_competency_queries.py --start-date 2020-01-01 --end-date 2026-12-31
    python scripts/run_competency_queries.py --query economic-evolution
    python scripts/run_competency_queries.py --output results/competency_report.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.competency_queries import CompetencyQueries
from src.utils.logger import get_logger

log = get_logger(__name__)


def format_results_for_display(results: dict) -> str:
    """Format query results for console display."""
    lines = []
    lines.append("=" * 80)
    lines.append("COMPETENCY QUERY RESULTS")
    lines.append("=" * 80)
    lines.append("")

    def format_section(title: str, data: any, indent: int = 0) -> None:
        prefix = "  " * indent
        lines.append(f"{prefix}{title}")
        lines.append(f"{prefix}{'-' * len(title)}")

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    lines.append(f"{prefix}{key}:")
                    format_section("", value, indent + 1)
                else:
                    lines.append(f"{prefix}{key}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data[:10], 1):  # Show first 10 items
                if isinstance(item, dict):
                    lines.append(f"{prefix}[{i}]")
                    for k, v in list(item.items())[:5]:  # Show first 5 fields
                        lines.append(f"{prefix}  {k}: {v}")
                else:
                    lines.append(f"{prefix}[{i}] {item}")
            if len(data) > 10:
                lines.append(f"{prefix}... ({len(data) - 10} more items)")
        else:
            lines.append(f"{prefix}{data}")

        lines.append("")

    for section_name, section_data in results.items():
        format_section(section_name.upper().replace("_", " "), section_data)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run competency queries on China-Romania temporal KG"
    )
    parser.add_argument(
        "--query",
        "-q",
        choices=[
            "all",
            "economic-evolution",
            "institutions",
            "bilateral-events",
            "credibility",
            "research",
        ],
        default="all",
        help="Which query to run (default: all)",
    )
    parser.add_argument(
        "--start-date",
        default="2020-01-01",
        help="Start date for temporal queries (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        default="2026-12-31",
        help="End date for temporal queries (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results for list queries",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (JSON format)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    log.info("Initializing competency queries...")
    queries = CompetencyQueries()

    results = {}

    try:
        if args.query in ("all", "economic-evolution"):
            log.info(
                "Query 1: How did China–Romania economic relations evolve "
                "from %s to %s?",
                args.start_date,
                args.end_date,
            )
            results["economic_evolution"] = queries.china_romania_economic_evolution(
                start_date=args.start_date,
                end_date=args.end_date,
            )

        if args.query in ("all", "institutions"):
            log.info(
                "Query 2: Which Romanian institutions were most connected "
                "to Chinese companies?"
            )
            results["romanian_institutions"] = (
                queries.romanian_institutions_connected_to_chinese_companies(
                    limit=args.limit,
                    start_date=args.start_date,
                    end_date=args.end_date,
                )
            )

        if args.query in ("all", "bilateral-events"):
            log.info(
                "Query 3: Which China–Romania events were reported "
                "from %s to %s?",
                args.start_date,
                args.end_date,
            )
            results["bilateral_events"] = queries.bilateral_events_in_period(
                start_date=args.start_date,
                end_date=args.end_date,
            )

        if args.query in ("all", "credibility"):
            log.info("Query 4: Which claims are unverified or contradicted?")
            results["credibility_analysis"] = (
                queries.contradicted_or_unverified_claims()
            )

        if args.query in ("all", "research"):
            log.info(
                "Query 5: Which collaborative research between China and Romania?"
            )
            results["collaborative_research"] = (
                queries.collaborative_research_authors(limit=args.limit)
            )

        # Output results
        if args.format == "json" or args.output:
            output_data = {
                "query_timestamp": datetime.now().isoformat(),
                "parameters": {
                    "query": args.query,
                    "start_date": args.start_date,
                    "end_date": args.end_date,
                    "limit": args.limit,
                },
                "results": results,
            }

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(output_data, indent=2, ensure_ascii=False)
                )
                log.info("Results written to %s", output_path)
            else:
                print(json.dumps(output_data, indent=2, ensure_ascii=False))
        else:
            # Text format
            print(format_results_for_display(results))

        log.info("Competency queries completed successfully")

    except Exception as exc:
        log.error("Failed to execute competency queries: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
