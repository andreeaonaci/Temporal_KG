"""
temporal_kg.src.ingestion.language_detector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Detects the language of article text using the ``langdetect`` library.
Falls back to "unknown" on failure or very short texts.

langdetect is non-deterministic by default; we seed it for reproducibility.
"""

from __future__ import annotations

from src.utils.logger import get_logger

log = get_logger(__name__)

_MIN_CHARS = 50   # don't attempt detection on very short strings
_SEED = 42


def detect_language(text: str) -> str:
    """
    Return the ISO 639-1 language code for *text* (e.g. "en", "ro", "zh-cn").
    Returns "unknown" when detection is not possible.
    """
    if not text or len(text.strip()) < _MIN_CHARS:
        return "unknown"

    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = _SEED
        return detect(text[:2000])   # first 2 KB is enough
    except Exception as exc:
        log.debug("Language detection failed: %s", exc)
        return "unknown"
