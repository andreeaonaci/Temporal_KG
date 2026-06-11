# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

from src.evaluation.report_generator import ReportGenerator


def test_report_generator_writes_json_and_csv(tmp_path):
    report = {
        "summary": {
            "entities": {
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
            }
        }
    }

    paths = ReportGenerator().write(report, output_dir=tmp_path)

    assert paths["json"].exists()
    assert paths["csv"].exists()
