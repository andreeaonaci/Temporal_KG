# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Plotly visualization helpers for temporal KG outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def plot_event_timeline(events: list[dict[str, Any]]):
    """Build a timeline plot for events with start/end dates."""
    rows = []
    for event in events:
        rows.append(
            {
                "event_id": event.get("event_id") or event.get("id"),
                "event_type": event.get("event_type") or event.get("type"),
                "start": event.get("start_date"),
                "end": event.get("end_date") or event.get("start_date"),
                "source": event.get("source_name") or "",
            }
        )
    frame = pd.DataFrame(rows)
    frame = frame.dropna(subset=["start"])
    if frame.empty:
        return None
    fig = px.timeline(
        frame,
        x_start="start",
        x_end="end",
        y="event_type",
        color="event_type",
        hover_data=["event_id", "source"],
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def plot_event_type_counts(events: list[dict[str, Any]]):
    """Build a bar chart of event type counts."""
    frame = pd.DataFrame(
        {"event_type": [e.get("event_type") or e.get("type") for e in events]}
    )
    if frame.empty:
        return None
    counts = frame.value_counts().reset_index(name="count")
    return px.bar(counts, x="event_type", y="count", color="event_type")
