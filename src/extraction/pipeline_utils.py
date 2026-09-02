# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Shared helpers for extraction-layer scripts and modules."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.utils.config import settings

# Dependency labels that mark a token as a core syntactic argument of a verb
# (subject, direct/indirect object, or the object of an attached
# preposition). Shared by the dependency-parse layers of both the event and
# relation extractors so participant/argument selection stays consistent.
CORE_ARG_DEPS = {"nsubj", "nsubjpass", "dobj", "pobj", "attr", "agent", "dative", "oprd"}


def dependency_argument_mentions(
    token: Any, sentence_mentions: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Group *sentence_mentions* overlapping a core syntactic argument of *token*.

    Returns a mapping from dependency label ("nsubj", "dobj", "pobj", ...) to
    the mentions whose character span overlaps that argument's subtree. Using
    the syntactic role (rather than "any entity anywhere in the sentence")
    is what distinguishes this from plain keyword co-occurrence.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}

    def _overlapping(span_start: int, span_end: int) -> list[dict[str, Any]]:
        return [
            mention
            for mention in sentence_mentions
            if mention["start_char"] < span_end and mention["end_char"] > span_start
        ]

    for child in token.children:
        dep = child.dep_
        if dep in CORE_ARG_DEPS:
            subtree = list(child.subtree)
            start_char = min(t.idx for t in subtree)
            end_char = max(t.idx + len(t.text) for t in subtree)
            hits = _overlapping(start_char, end_char)
            if hits:
                grouped.setdefault(dep, []).extend(hits)
        elif dep == "prep":
            for grandchild in child.children:
                if grandchild.dep_ == "pobj":
                    subtree = list(grandchild.subtree)
                    start_char = min(t.idx for t in subtree)
                    end_char = max(t.idx + len(t.text) for t in subtree)
                    hits = _overlapping(start_char, end_char)
                    if hits:
                        grouped.setdefault("pobj", []).extend(hits)
    return grouped


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
    *,
    only_relevant: bool = True,
) -> Iterable[dict[str, Any]]:
    """Yield cleaned article JSON records from the processed directory.

    Every extraction script (entity/temporal/event/relation) uses this as
    its sole source of input articles, so this is the one place that needs
    to respect RelevanceFilter's is_relevant flag -- and until now it
    didn't. RelevanceFilter correctly marks a China-only or Romania-only
    article as is_relevant=False at ingestion time (see relevance_reason,
    e.g. "china_only"), but this function ignored that and yielded every
    stored article regardless, so irrelevant articles flowed into
    extraction, corroboration, and veracity scoring exactly like relevant
    ones. Confirmed as real contamination (2026-08-20): after a historical
    GDELT backfill, several "contested" corroboration groups turned out to
    be genuinely unrelated China-only stories (a Shanghai auto show, a
    tiger-park exhibit, a Singapore Exchange CEO interview) that correctly
    failed relevance filtering at ingestion and should never have reached
    this stage. Default is the fix (only_relevant=True); pass False only
    for debugging/auditing what got filtered out.
    """
    base_dir = input_dir or settings.abs_path("paths.data_processed")
    if not base_dir.exists():
        return
    for path in sorted(base_dir.rglob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        if only_relevant and not article.get("is_relevant"):
            continue
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
