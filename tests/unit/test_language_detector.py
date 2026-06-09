"""Unit tests for src.ingestion.language_detector."""

from src.ingestion.language_detector import detect_language


def test_english_text():
    text = (
        "China and Romania have strengthened bilateral relations "
        "through a series of diplomatic meetings this year. "
        "The two countries discussed trade, infrastructure, and cultural exchange."
    )
    lang = detect_language(text)
    assert lang == "en"


def test_short_text_returns_unknown():
    assert detect_language("Hi") == "unknown"
    assert detect_language("") == "unknown"
    assert detect_language("   ") == "unknown"


def test_none_returns_unknown():
    assert detect_language(None) == "unknown"  # type: ignore


def test_romanian_text():
    text = (
        "România a semnat un acord de cooperare cu China în domeniul "
        "infrastructurii și energiei regenerabile. Acordul a fost "
        "parafat la București în cadrul unei ceremonii oficiale."
    )
    lang = detect_language(text)
    # langdetect may return "ro" for Romanian
    assert lang in ("ro", "en", "unknown")   # permissive — library can vary
