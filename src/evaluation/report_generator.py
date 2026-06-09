"""Summary report generation for evaluation outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class ReportGenerator:
    """Write JSON and CSV evaluation summaries."""

    def write(
        self,
        report: dict[str, Any],
        *,
        output_dir: Path,
        stem: str = "evaluation",
    ) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{stem}.json"
        csv_path = output_dir / f"{stem}.csv"
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "scope",
                    "metric",
                    "precision",
                    "recall",
                    "f1",
                    "accuracy",
                    "correct",
                    "predicted_total",
                    "gold_total",
                    "true_positive",
                    "total",
                ],
            )
            writer.writeheader()
            for metric_name, values in report.get("summary", {}).items():
                row = {"scope": "summary", "metric": metric_name}
                row.update(values)
                writer.writerow(row)
        return {"json": json_path, "csv": csv_path}
