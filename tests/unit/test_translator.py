"""Unit tests for src.ingestion.translator."""

import pytest
from unittest.mock import patch, MagicMock
from src.ingestion.models import ArticleRecord
from src.ingestion.translator import (
    Translator,
    _chunk_text,
    _translate_text,
    _translate_text_with_status,
)


# ── _chunk_text ───────────────────────────────────────────────────────────────

def test_chunk_text_short_string():
    result = _chunk_text("hello world", size=100)
    assert result == ["hello world"]


def test_chunk_text_splits_on_newline():
    text = "line1\nline2\nline3\n"
    chunks = _chunk_text(text, size=10)
    # Each chunk must be within size
    for chunk in chunks:
        assert len(chunk) <= 10 + len("line3\n")   # tolerance for last line


def test_chunk_text_reassembles():
    text = "\n".join([f"This is sentence number {i}." for i in range(100)])
    chunks = _chunk_text(text, size=200)
    assert "".join(chunks) == text


# ── _translate_text ───────────────────────────────────────────────────────────

def test_translate_text_skips_empty():
    assert _translate_text("", "ro") == ""
    assert _translate_text("   ", "ro").strip() == ""


def test_translate_text_returns_original_on_import_error():
    with patch.dict("sys.modules", {"deep_translator": None}):
        result = _translate_text("Bună ziua", "ro")
    assert result == "Bună ziua"


def test_translate_text_calls_google_translator():
    mock_translator = MagicMock()
    mock_translator.translate.return_value = "Good morning"
    mock_module = MagicMock()
    mock_module.GoogleTranslator.return_value = mock_translator

    with patch.dict("sys.modules", {"deep_translator": mock_module}):
        result = _translate_text("Bună dimineața", "ro")

    assert result == "Good morning"
    mock_translator.translate.assert_called_once()


def test_translate_text_retries_on_failure():
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = [Exception("network"), "Hello"]
    mock_module = MagicMock()
    mock_module.GoogleTranslator.return_value = mock_translator

    with patch.dict("sys.modules", {"deep_translator": mock_module}), \
         patch("src.ingestion.translator.time.sleep"):
        result = _translate_text("Salut", "ro")

    assert result == "Hello"


def test_translate_text_returns_original_after_max_retries():
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = Exception("always fails")
    mock_module = MagicMock()
    mock_module.GoogleTranslator.return_value = mock_translator

    with patch.dict("sys.modules", {"deep_translator": mock_module}), \
         patch("src.ingestion.translator.time.sleep"):
        result = _translate_text("Salut", "ro")

    assert result == "Salut"   # original preserved


def test_translate_text_with_status_reports_failure():
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = Exception("always fails")
    mock_module = MagicMock()
    mock_module.GoogleTranslator.return_value = mock_translator

    with patch.dict("sys.modules", {"deep_translator": mock_module}), \
         patch("src.ingestion.translator.time.sleep"):
        result, ok = _translate_text_with_status("Salut", "ro")

    assert result == "Salut"
    assert ok is False


# ── Translator class ──────────────────────────────────────────────────────────

def make_article(lang="ro", title="Bună ziua", content="Conținut în română."):
    return ArticleRecord(
        url="https://example.com/test",
        title=title,
        content_clean=content,
        language=lang,
    )


def test_translator_skips_english():
    t = Translator()
    art = make_article(lang="en", title="Hello", content="English content.")
    with patch("src.ingestion.translator._translate_text") as mock_tr:
        t.translate(art)
    mock_tr.assert_not_called()
    assert art.title == "Hello"


def test_translator_skips_unknown():
    t = Translator()
    art = make_article(lang="unknown")
    with patch(
        "src.ingestion.translator._translate_text_with_status",
        return_value=("Translated text", True),
    ) as mock_tr:
        t.translate(art)
    assert mock_tr.call_count == 2
    assert mock_tr.call_args_list[0][0][1] == "auto"


def test_translator_translates_romanian():
    t = Translator()
    art = make_article(lang="ro")

    with patch(
        "src.ingestion.translator._translate_text_with_status",
        return_value=("Translated text", True),
    ) as mock_tr:
        t.translate(art)

    assert mock_tr.call_count == 2   # title + content
    assert art.title == "Translated text"
    assert art.content_clean == "Translated text"


def test_translator_normalises_chinese_code():
    t = Translator()
    art = make_article(lang="zh-cn", title="你好", content="中文内容")

    with patch(
        "src.ingestion.translator._translate_text_with_status",
        return_value=("Hello", True),
    ) as mock_tr:
        t.translate(art)

    # Should be called with "zh-CN" not "zh-cn"
    calls = mock_tr.call_args_list
    assert calls[0][0][1] == "zh-CN"


def test_translator_disabled_via_settings():
    with patch("src.ingestion.translator.settings", side_effect=lambda k, d=None: False if k == "ingestion.translate_to_english" else d):
        t = Translator()
    art = make_article(lang="ro")
    with patch("src.ingestion.translator._translate_text") as mock_tr:
        t.translate(art)
    mock_tr.assert_not_called()


def test_translator_marks_relevance_reason():
    t = Translator()
    art = make_article(lang="ro")
    art.relevance_reason = "china+romania_co-occurrence"

    with patch("src.ingestion.translator._translate_text", return_value="translated"):
        t.translate(art)

    assert "translated_from_ro" in art.relevance_reason
    assert "china+romania_co-occurrence" in art.relevance_reason


def test_translator_raises_when_translation_required_and_fails():
    t = Translator()
    art = make_article(lang="ro")

    with patch("src.ingestion.translator._translate_text_with_status", return_value=("orig", False)):
        with pytest.raises(RuntimeError):
            t.translate(art)
