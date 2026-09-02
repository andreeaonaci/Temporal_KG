#!/usr/bin/env bash
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.
#
# End-to-end real-data experiment: ingestion -> extraction -> corroboration
# (semantic merge + NLI contradiction + temporal gate + lifecycle
# verification, all wired in) -> veracity scoring -> real candidate-pair
# mining for blind human review.
#
# Run this in your WSL myenv (the ingestion stack -- GDELT, feedparser,
# deep-translator, langdetect -- lives there, not in the Windows dev venv).
#
# GDELT's Full-Text Search API caps at 250 records per query regardless of
# the date range requested, so a single ingestion call will not get you
# real volume -- this loops ingestion across quarters to accumulate more
# than that, deduplicating by URL against what's already in the DB (see
# run_ingestion.py's articles_new/articles_dup stats).
#
# Historical range confirmed working by hand (2026-08-19): a clean,
# properly-spaced query for Jan-Apr 2020 returned real articles -- the
# quarterly loop below going back to 2017 (GDELT's DOC 2.0 full-text index
# coverage start) is genuine historical backfill, not a guess. An earlier
# version of this script reported "0 results for every quarter" back to
# 2023, which was purely the rate-limit bug fixed in gdelt_fetcher.py/
# settings.yaml (gdelt.rate_limit_delay), not a real absence of data --
# don't assume empty quarters mean "no coverage" unless you've confirmed
# it's not that same class of bug recurring.
#
# Usage:
#   bash scripts/run_big_experiment.sh                 # ingest 2017-01-01..today, then run the pipeline
#   bash scripts/run_big_experiment.sh --skip-ingestion # reuse whatever's already in data/processed

set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_INGESTION=false
for arg in "$@"; do
  if [[ "$arg" == "--skip-ingestion" ]]; then
    SKIP_INGESTION=true
  fi
done

if [[ "$SKIP_INGESTION" == "false" ]]; then
  echo "=== RSS ingestion (one pass -- not date-scoped, so it must NOT run inside the ==="
  echo "=== quarterly GDELT loop below: RSS feeds return the same ~100 results        ==="
  echo "=== regardless of which GDELT quarter is being processed, so running it once  ==="
  echo "=== per quarter (an earlier version of this script did, via --sources         ==="
  echo "=== defaulting to \"all\") wasted ~3-4 minutes of redundant Google News URL     ==="
  echo "=== resolution per quarter for no benefit -- ~2+ hours wasted across the full  ==="
  echo "=== 2017-today loop before this was caught (2026-08-20).                      ==="
  python scripts/run_ingestion.py --sources rss --no-progress

  echo ""
  echo "=== GDELT ingestion (quarterly chunks, 2017-01-01 through today) ==="
  START_YEAR=2017
  END_YEAR=$(date +%Y)
  for year in $(seq "$START_YEAR" "$END_YEAR"); do
    for q_start in "01-01" "04-01" "07-01" "10-01"; do
      case "$q_start" in
        "01-01") q_end="03-31" ;;
        "04-01") q_end="06-30" ;;
        "07-01") q_end="09-30" ;;
        "10-01") q_end="12-31" ;;
      esac
      start_date="${year}-${q_start}"
      end_date="${year}-${q_end}"
      if [[ "$start_date" > "$(date +%Y-%m-%d)" ]]; then
        continue
      fi
      echo "--- ${start_date} .. ${end_date} ---"
      python scripts/run_ingestion.py --sources gdelt --start "$start_date" --end "$end_date" --max 250 --no-progress || \
        echo "  (query failed or rate-limited, continuing with next quarter)"
      # GDELT enforces one request every 5 seconds; each run_ingestion.py
      # call is a fresh process, so the fetcher's own internal delay
      # (settings.yaml gdelt.rate_limit_delay) doesn't carry over between
      # loop iterations -- without this, every query after the first in
      # this loop gets silently rate-limited (non-JSON response, reads as
      # "0 new / 0 dup / 0 relevant / 0 errors").
      sleep 8
    done
  done
else
  echo "=== Skipping ingestion (--skip-ingestion) ==="
fi

echo ""
echo "=== Entity extraction ==="
python scripts/run_entity_extraction.py

echo ""
echo "=== Temporal extraction ==="
python scripts/run_temporal_extraction.py

echo ""
echo "=== Event extraction ==="
python scripts/run_event_extraction.py

echo ""
echo "=== Relation extraction ==="
python scripts/run_relation_extraction.py

echo ""
echo "=== Corroboration analysis (semantic merge + NLI contradiction + temporal gate + lifecycle verification) ==="
python scripts/run_corroboration_analysis.py

echo ""
echo "=== Veracity / fake-news assessment ==="
python scripts/run_fake_news_analysis.py

echo ""
echo "=== Mining real candidate pairs for blind human review ==="
python scripts/mine_real_candidate_pairs.py \
  --entities-dir data/exports/entities \
  --temporals-dir data/exports/temporals \
  --events-dir data/exports/events \
  --out data/exports/mined_candidate_pairs.json \
  --record-type claims \
  --min-support 2

echo ""
echo "=== Done. Article/entity/event counts: ==="
echo "Processed articles: $(find data/processed -name '*.json' 2>/dev/null | wc -l)"
echo "Entity payloads:    $(find data/exports/entities -name '*.json' 2>/dev/null | wc -l)"
echo "Event payloads:     $(find data/exports/events -name '*.json' 2>/dev/null | wc -l)"
echo ""
echo "Next step: label the real mined pairs blind, then check agreement:"
echo "  python scripts/label_pairs.py --fixture data/exports/mined_candidate_pairs.json \\"
echo "    --schema corroboration --annotator <name> --out data/exports/mined_pairs.<name>.json"
