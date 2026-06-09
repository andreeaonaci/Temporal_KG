from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.reporting.helpers import (
    chart_event_type_distribution,
    chart_source_activity,
    chart_volume_over_time,
    load_json_exports,
)


def test_reporting_helpers_return_plot_ready_series(tmp_path):
    export_dir = tmp_path / "events"
    export_dir.mkdir()
    (export_dir / "article-1.events.json").write_text(
        (
            '{"article_id":"article-1","events":['
            '{"event_type":"DiplomaticMeeting"}]}'
        ),
        encoding="utf-8",
    )

    frame = pd.DataFrame(
        [
            {"published_at": "2025-05-01", "source_name": "Reuters"},
            {"published_at": "2025-05-15", "source_name": "BBC"},
        ]
    )

    assert not load_json_exports(Path(export_dir)).empty
    assert chart_volume_over_time(frame).sum() == 2
    assert chart_source_activity(frame).sum() == 2
    assert chart_event_type_distribution(
        [{"event_type": "DiplomaticMeeting"}]
    ).iloc[0] == 1
