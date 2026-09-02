# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Regression test for iter_cleaned_articles ignoring is_relevant.

Confirmed as real contamination (2026-08-20): every extraction script uses
this function as its sole input source, and it used to yield every article
in data/processed/ regardless of RelevanceFilter's is_relevant flag --
letting genuinely irrelevant articles (a China-only story with no Romania
mention, correctly flagged is_relevant=False, relevance_reason="china_only"
at ingestion) flow into entity/event extraction, corroboration, and
veracity scoring exactly like real China-Romania claims.
"""

from __future__ import annotations

import json

from src.extraction.pipeline_utils import iter_cleaned_articles


def _write_article(directory, filename, *, is_relevant, url="https://example.com/x"):
    (directory / filename).write_text(
        json.dumps({"url": url, "title": "t", "content_clean": "c", "is_relevant": is_relevant}),
        encoding="utf-8",
    )


def test_irrelevant_articles_are_excluded_by_default(tmp_path):
    _write_article(tmp_path, "relevant.json", is_relevant=True, url="https://example.com/relevant")
    _write_article(tmp_path, "irrelevant.json", is_relevant=False, url="https://example.com/irrelevant")

    articles = list(iter_cleaned_articles(tmp_path))

    urls = {a["url"] for a in articles}
    assert urls == {"https://example.com/relevant"}


def test_only_relevant_false_yields_everything_for_debugging(tmp_path):
    _write_article(tmp_path, "relevant.json", is_relevant=True, url="https://example.com/relevant")
    _write_article(tmp_path, "irrelevant.json", is_relevant=False, url="https://example.com/irrelevant")

    articles = list(iter_cleaned_articles(tmp_path, only_relevant=False))

    urls = {a["url"] for a in articles}
    assert urls == {"https://example.com/relevant", "https://example.com/irrelevant"}


def test_missing_is_relevant_field_is_treated_as_not_relevant(tmp_path):
    # Defensive default: an article record with no is_relevant key at all
    # (malformed or from an older schema) should not silently pass through.
    (tmp_path / "no_flag.json").write_text(
        json.dumps({"url": "https://example.com/no-flag", "title": "t", "content_clean": "c"}),
        encoding="utf-8",
    )

    articles = list(iter_cleaned_articles(tmp_path))
    assert articles == []


def test_empty_directory_yields_nothing(tmp_path):
    assert list(iter_cleaned_articles(tmp_path)) == []
