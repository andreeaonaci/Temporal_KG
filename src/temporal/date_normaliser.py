# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Temporal expression normalization helpers."""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta
from typing import Any

from dateutil import parser as dateutil_parser

from src.utils.logger import get_logger

log = get_logger(__name__)

MONTH_ALIASES = {
    "ianuarie": "January",
    "februarie": "February",
    "martie": "March",
    "aprilie": "April",
    "mai": "May",
    "iunie": "June",
    "iulie": "July",
    "august": "August",
    "septembrie": "September",
    "octombrie": "October",
    "noiembrie": "November",
    "decembrie": "December",
}
RELATIVE_MAP = {
    "yesterday": (-1, "day"),
    "ieri": (-1, "day"),
    "today": (0, "day"),
    "today,": (0, "day"),
    "astăzi": (0, "day"),
    "azi": (0, "day"),
    "tomorrow": (1, "day"),
    "mâine": (1, "day"),
    "maine": (1, "day"),
}


class DateNormaliser:
    """Best-effort normalizer for article temporal expressions."""

    def normalise(self, raw: str, reference: datetime | None = None) -> dict[str, Any]:
        ref = reference or datetime.utcnow()
        text = (raw or "").strip()
        result = {
            "raw": raw,
            "kind": None,
            "value": None,
            "granularity": None,
            "confidence": 0.0,
            "resolved": False,
            "ambiguous": False,
            "anchor_date": ref.date().isoformat(),
            "reason": None,
        }
        if not text:
            result["ambiguous"] = True
            result["reason"] = "empty_expression"
            return result

        lowered = text.lower().strip()
        if lowered in RELATIVE_MAP:
            offset, granularity = RELATIVE_MAP[lowered]
            target = ref.date() + timedelta(days=offset)
            result.update(
                {
                    "kind": "relative_date",
                    "value": target.isoformat(),
                    "granularity": granularity,
                    "confidence": 0.96,
                    "resolved": True,
                }
            )
            return result

        relative_interval = self._normalise_relative_interval(lowered, ref)
        if relative_interval:
            return {**result, **relative_interval}

        duration = self._normalise_duration(lowered)
        if duration:
            return {**result, **duration}

        interval = self._normalise_interval(text, ref)
        if interval:
            return {**result, **interval}

        deadline = self._normalise_deadline(text, ref)
        if deadline:
            return {**result, **deadline}

        absolute = self._normalise_absolute(text, ref)
        if absolute:
            return {**result, **absolute}

        result["ambiguous"] = True
        result["reason"] = "unresolved_expression"
        return result

    def _normalise_absolute(
        self, text: str, reference: datetime
    ) -> dict[str, Any] | None:
        prepared = self._translate_months(text)
        prepared = re.sub(r"\b(early|late|mid)\s+", "", prepared, flags=re.IGNORECASE)
        try:
            dt = dateutil_parser.parse(prepared, default=reference, fuzzy=False)
        except (ValueError, OverflowError):
            year_match = re.fullmatch(r"\d{4}", text.strip())
            if year_match:
                return {
                    "kind": "absolute_date",
                    "value": text.strip(),
                    "granularity": "year",
                    "confidence": 0.82,
                    "resolved": True,
                }
            month_year = re.fullmatch(r"([A-Za-zăâîșțĂÂÎȘȚ]+)\s+(\d{4})", text.strip())
            if month_year:
                month_name = self._translate_months(month_year.group(1))
                try:
                    month_index = list(calendar.month_name).index(month_name)
                except ValueError:
                    return None
                return {
                    "kind": "absolute_date",
                    "value": f"{month_year.group(2)}-{month_index:02d}",
                    "granularity": "month",
                    "confidence": 0.84,
                    "resolved": True,
                }
            return None

        if re.search(r"\b\d{4}\b", text) and not re.search(r"\b\d{1,2}:\d{2}\b", text):
            if re.search(r"\b\d{1,2}\b", text):
                granularity = "day"
                value = dt.date().isoformat()
            elif self._contains_month(text):
                granularity = "month"
                value = dt.strftime("%Y-%m")
            else:
                granularity = "year"
                value = dt.strftime("%Y")
            return {
                "kind": "absolute_date",
                "value": value,
                "granularity": granularity,
                "confidence": 0.9 if granularity == "day" else 0.84,
                "resolved": True,
            }
        return None

    def _normalise_relative_interval(
        self, lowered: str, reference: datetime
    ) -> dict[str, Any] | None:
        if lowered in {"last week", "săptămâna trecută", "saptamana trecuta"}:
            end = reference.date() - timedelta(days=reference.weekday() + 1)
            start = end - timedelta(days=6)
            return {
                "kind": "relative_interval",
                "value": {"start": start.isoformat(), "end": end.isoformat()},
                "granularity": "week",
                "confidence": 0.9,
                "resolved": True,
            }
        if lowered in {"next week", "săptămâna viitoare", "saptamana viitoare"}:
            start = reference.date() + timedelta(days=(7 - reference.weekday()))
            end = start + timedelta(days=6)
            return {
                "kind": "relative_interval",
                "value": {"start": start.isoformat(), "end": end.isoformat()},
                "granularity": "week",
                "confidence": 0.88,
                "resolved": True,
            }
        if lowered in {"last month", "luna trecută", "luna trecuta"}:
            year = reference.year
            month = reference.month - 1 or 12
            if reference.month == 1:
                year -= 1
            return {
                "kind": "relative_interval",
                "value": {
                    "start": f"{year}-{month:02d}-01",
                    "end": f"{year}-{month:02d}",
                },
                "granularity": "month",
                "confidence": 0.86,
                "resolved": True,
            }
        return None

    def _normalise_interval(
        self, text: str, reference: datetime
    ) -> dict[str, Any] | None:
        match = re.search(
            r"(?:from|between|din|între)\s+(.+?)\s+(?:to|and|până\s+în|pana\s+in|și|si)\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        start = self._normalise_absolute(match.group(1).strip(), reference)
        end = self._normalise_absolute(match.group(2).strip(), reference)
        if not start and end and end.get("granularity") in {"month", "day"}:
            end_year = str(end["value"]).split("-")[0]
            start = self._normalise_absolute(
                f"{match.group(1).strip()} {end_year}", reference
            )
        if not start or not end:
            return {
                "kind": "interval",
                "value": None,
                "granularity": None,
                "confidence": 0.45,
                "resolved": False,
                "ambiguous": True,
                "reason": "partial_interval_resolution",
            }
        return {
            "kind": "interval",
            "value": {"start": start["value"], "end": end["value"]},
            "granularity": start.get("granularity") or end.get("granularity"),
            "confidence": min(start["confidence"], end["confidence"]),
            "resolved": True,
        }

    def _normalise_deadline(
        self, text: str, reference: datetime
    ) -> dict[str, Any] | None:
        match = re.search(
            r"(?:until|by|through|valid until|până\s+în|pana\s+in|valabil\s+până\s+la)\s+(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        normalized = self._normalise_absolute(match.group(1).strip(), reference)
        if not normalized:
            return {
                "kind": "deadline",
                "value": None,
                "granularity": None,
                "confidence": 0.4,
                "resolved": False,
                "ambiguous": True,
                "reason": "unresolved_deadline",
            }
        return {
            "kind": "deadline",
            "value": {"end": normalized["value"]},
            "granularity": normalized["granularity"],
            "confidence": normalized["confidence"],
            "resolved": True,
        }

    def _normalise_duration(self, lowered: str) -> dict[str, Any] | None:
        match = re.search(
            r"(?:for|within|timp\s+de)\s+(\d+)\s+(day|days|week|weeks|month|months|year|years|zile|săptămâni|saptamani|luni|ani)",
            lowered,
        )
        if not match:
            return None
        number = int(match.group(1))
        unit = match.group(2)
        designator = "D"
        if (
            unit.startswith("week")
            or unit.startswith("săpt")
            or unit.startswith("sapt")
        ):
            designator = "W"
        elif unit.startswith("month") or unit.startswith("luni"):
            designator = "M"
        elif unit.startswith("year") or unit.startswith("ani"):
            designator = "Y"
        return {
            "kind": "duration",
            "value": f"P{number}{designator}",
            "granularity": "duration",
            "confidence": 0.87,
            "resolved": True,
        }

    @staticmethod
    def _translate_months(text: str) -> str:
        result = text
        for ro_month, en_month in MONTH_ALIASES.items():
            result = re.sub(rf"\b{ro_month}\b", en_month, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def _contains_month(text: str) -> bool:
        lowered = text.lower()
        return any(
            month.lower() in lowered for month in list(calendar.month_name)[1:]
        ) or any(month in lowered for month in MONTH_ALIASES)
