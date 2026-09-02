#!/usr/bin/env bash
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.
#
# GDELT-only re-run of the 2017-today quarterly backfill loop (RSS already
# succeeded in the prior full run; this just retries the GDELT half after
# api.gdeltproject.org came back up / stopped hanging on the DOC API).
set -uo pipefail
cd "$(dirname "$0")/.."

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
    sleep 8
  done
done
echo "=== GDELT retry loop done ==="
