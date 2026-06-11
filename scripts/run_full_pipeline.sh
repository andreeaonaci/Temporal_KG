#!/usr/bin/env bash
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

# One-command launcher for the full Temporal KG pipeline.
# Uses an advanced default profile and forwards any extra CLI args.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v conda >/dev/null 2>&1; then
  echo "ERROR: conda is not installed or not in PATH." >&2
  exit 1
fi

# Enable `conda activate` in non-interactive shell.
eval "$(conda shell.bash hook)"
conda activate temporal_kg

LOG_DIR="${PROJECT_ROOT}/logs/pipeline"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/full_pipeline_$(date -u +%Y%m%d_%H%M%S).log"

echo "Pipeline log: ${LOG_FILE}"

# Advanced defaults: full pipeline with richer temporal extraction,
# graph loading, and competency reporting enabled by default.
python -u "${PROJECT_ROOT}/scripts/run_full_pipeline.py" \
  --temporal-engine heideltime \
  --fallback-temporal-engine regex \
  --credibility-threshold 0.3 \
  --fake-news-threshold 0.9 \
  --continue-on-error \
  --with-deepke \
  --with-neo4j-load \
  --with-competency-queries \
  "$@" 2>&1 | tee "${LOG_FILE}"

PIPELINE_EXIT=${PIPESTATUS[0]}

if [[ ${PIPELINE_EXIT} -ne 0 ]]; then
  echo "Pipeline finished with errors (exit=${PIPELINE_EXIT})."
  echo "Check log: ${LOG_FILE}"
else
  echo "Pipeline finished successfully."
  echo "Log saved to: ${LOG_FILE}"
fi

exit ${PIPELINE_EXIT}
