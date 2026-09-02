# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Tests for Google News wrapper-URL resolution.

The decoder itself (googlenewsdecoder) is a third-party unofficial package
hitting a live Google endpoint -- not mocked here, since the point of these
tests is the fail-soft wrapping logic around it (non-wrapper URLs pass
through untouched, decode failures fall back to the original URL, disabled
via settings skips resolution entirely), not the decoder's own correctness.
A single live-network confirmation was done by hand during development
(see the module docstring) rather than baked into the test suite, since a
real network dependency in a unit test is exactly what these tests are
designed to avoid needing.
"""

from __future__ import annotations

from src.ingestion.google_news_resolver import is_google_news_wrapper, resolve


def test_is_google_news_wrapper_detects_the_real_host():
    assert is_google_news_wrapper("https://news.google.com/rss/articles/CBMi123") is True


def test_is_google_news_wrapper_rejects_other_hosts():
    assert is_google_news_wrapper("https://www.reuters.com/world/some-article") is False
    assert is_google_news_wrapper("https://news.google.com.evil.example.com/x") is False


def test_is_google_news_wrapper_handles_malformed_url_gracefully():
    assert is_google_news_wrapper("not a url at all") is False


def test_resolve_passes_through_non_wrapper_urls_unchanged():
    url = "https://www.reuters.com/world/some-article"
    assert resolve(url) == url


def test_resolve_skips_decoding_when_disabled_via_settings(monkeypatch):
    monkeypatch.setattr(
        "src.ingestion.google_news_resolver.settings",
        lambda key, default=None: False if key == "ingestion.resolve_google_news_urls" else default,
    )
    url = "https://news.google.com/rss/articles/CBMi123"
    assert resolve(url) == url


def test_resolve_falls_back_to_wrapper_url_when_decoder_raises(monkeypatch):
    monkeypatch.setattr("src.ingestion.google_news_resolver.settings", lambda key, default=None: True)

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated decoder failure")

    # Patch the import target the function reaches for internally.
    import sys
    import types

    fake_module = types.ModuleType("googlenewsdecoder")
    fake_module.gnewsdecoder = _raise
    monkeypatch.setitem(sys.modules, "googlenewsdecoder", fake_module)

    url = "https://news.google.com/rss/articles/CBMi123"
    assert resolve(url) == url


def test_resolve_falls_back_when_decoder_reports_failure_status(monkeypatch):
    monkeypatch.setattr("src.ingestion.google_news_resolver.settings", lambda key, default=None: True)

    import sys
    import types

    fake_module = types.ModuleType("googlenewsdecoder")
    fake_module.gnewsdecoder = lambda url, interval=None: {"status": False, "message": "nope"}
    monkeypatch.setitem(sys.modules, "googlenewsdecoder", fake_module)

    url = "https://news.google.com/rss/articles/CBMi123"
    assert resolve(url) == url


def test_resolve_returns_decoded_url_on_success(monkeypatch):
    monkeypatch.setattr("src.ingestion.google_news_resolver.settings", lambda key, default=None: True)

    import sys
    import types

    fake_module = types.ModuleType("googlenewsdecoder")
    fake_module.gnewsdecoder = lambda url, interval=None: {
        "status": True,
        "decoded_url": "https://real-publisher.example.com/article",
    }
    monkeypatch.setitem(sys.modules, "googlenewsdecoder", fake_module)

    url = "https://news.google.com/rss/articles/CBMi123"
    assert resolve(url) == "https://real-publisher.example.com/article"
