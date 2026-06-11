#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
generate_latest_month_by_type.py

Creates:
    latest_month_by_type.png

using the existing TemporalGraphQueries API.
"""

from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
import plotly.io as pio

from src.graph.query_layer import TemporalGraphQueries
from src.utils.logger import get_logger

log = get_logger(__name__)

COLORS = {
    "DiplomaticMeeting": "#378ADD",
    "TradeAgreement": "#639922",
    "InvestmentProject": "#BA7517",
    "SecurityStatement": "#E24B4A",
    "PolicyStatement": "#7F77DD",
    "TechnologyCooperation": "#1D9E75",
    "InfrastructureProject": "#888780",
    "CompanyActivity": "#D4537E",
    "EducationCooperation": "#5DCAA5",
    "CulturalExchange": "#D85A30",
    "SanctionOrRestriction": "#B22222",
}

START_DATE = "2026-06-01"
END_DATE = "2026-06-30"


def extract_event_type(event):
    """
    Tries several common field names.
    """

    for field in (
        "event_type",
        "type",
        "EventType",
        "category",
        "eventCategory",
    ):
        if isinstance(event, dict) and field in event:
            return event[field]

    return "Unknown"


def load_counts():
    queries = TemporalGraphQueries()

    events = queries.events_within_date_range(
        start_date=START_DATE,
        end_date=END_DATE,
    )

    print(f"Retrieved {len(events)} events")

    if not events:
        return {}

    print("\nSample event:")
    print(events[0])

    counts = Counter()

    for event in events:
        counts[extract_event_type(event)] += 1

    return dict(counts)


def create_chart(type_counts):
    if not type_counts:
        print("No data found.")
        return

    sorted_types = sorted(
        type_counts.keys(),
        key=lambda x: type_counts[x]
    )

    counts = [type_counts[t] for t in sorted_types]

    colors = [
        COLORS.get(t, "#AAAAAA")
        for t in sorted_types
    ]

    fig = go.Figure(
        go.Bar(
            x=counts,
            y=sorted_types,
            orientation="h",
            marker_color=colors,
            text=counts,
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Event Counts by Type (June 2026)",
        xaxis_title="Number of Events",
        yaxis_title="Event Type",
        plot_bgcolor="white",
        paper_bgcolor="white",
        width=1000,
        height=650,
        margin=dict(l=220, r=80, t=70, b=50),
        showlegend=False,
    )

    output = Path("latest_month_by_type.png")

    pio.write_image(
        fig,
        str(output),
        scale=2,
    )

    print(f"\nSaved: {output.resolve()}")


def main():
    counts = load_counts()

    print("\nCounts by type:\n")

    for event_type, count in sorted(
        counts.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(f"{event_type:<30} {count}")

    create_chart(counts)


if __name__ == "__main__":
    main()