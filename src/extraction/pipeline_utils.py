"""Shared helpers for extraction-layer scripts and modules."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.utils.config import settings


def stable_id(*parts: Any) -> str:
    """Return a deterministic identifier for the provided values."""
    digest = hashlib.sha256(
        "||".join(str(part or "") for part in parts).encode("utf-8")
    ).hexdigest()
    return digest[:24]


def stable_json(value: Any) -> str:
    """Serialize a value deterministically for signatures and exports."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def build_event_signature(
    event: dict[str, Any],
    temporal: dict[str, Any] | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Return a transparent cross-article signature for similar events."""
    participants = sorted(event.get("participant_entity_ids") or [])
    time_key = start_date or end_date
    if not time_key and temporal:
        time_key = (
            temporal.get("normalized")
            if not isinstance(temporal.get("normalized"), (dict, list))
            else stable_json(temporal.get("normalized"))
        )
    return stable_id(
        event.get("event_type"),
        event.get("normalized_trigger"),
        "|".join(participants),
        time_key or "undated",
    )


def build_claim_signature(
    sentence: str,
    *,
    event_type: str | None = None,
    event_signature: str | None = None,
) -> str:
    """Return a stable signature for a sentence-level factual claim."""
    normalized = " ".join((sentence or "").lower().split())
    return stable_id(
        "claim",
        event_type or "",
        event_signature or "",
        normalized,
    )


def get_article_id(article: dict[str, Any]) -> str:
    """Build a stable article id from persisted article fields."""
    return (
        article.get("article_id")
        or article.get("url_hash")
        or stable_id(article.get("url"), article.get("published_at"))
    )


def parse_article_datetime(article: dict[str, Any]) -> datetime | None:
    """Parse the article publication date when present."""
    raw = article.get("published_at") or article.get("fetched_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def iter_cleaned_articles(
    input_dir: Path | None = None,
) -> Iterable[dict[str, Any]]:
    """Yield cleaned article JSON records from the processed directory."""
    base_dir = input_dir or settings.abs_path("paths.data_processed")
    if not base_dir.exists():
        return
    for path in sorted(base_dir.rglob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        article.setdefault("article_id", get_article_id(article))
        article.setdefault("json_source_path", str(path))
        yield article


def write_json_output(
    payload: dict[str, Any], base_dir: Path, article_id: str, stem: str
) -> Path:
    """Persist extraction output to a deterministic JSON path."""
    base_dir.mkdir(parents=True, exist_ok=True)
    target = base_dir / f"{article_id}.{stem}.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def load_json_by_article(directory: Path) -> dict[str, dict[str, Any]]:
    """Load article-keyed JSON payloads from a directory tree."""
    results: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return results
    for path in sorted(directory.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        article_id = payload.get("article_id")
        if article_id:
            results[article_id] = payload
    return results
