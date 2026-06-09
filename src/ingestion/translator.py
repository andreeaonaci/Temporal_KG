"""
temporal_kg.src.ingestion.translator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Translates article title and content to English using Google Translate
via the ``deep-translator`` library (no API key required).

Rules
-----
- If language is "en" → skip
- If language is "unknown" and enabled, use auto source detection
- Translates in chunks to stay within the 5000-char limit per request
- Normalizes article.language to target language after successful translation
- On translation failure, can fail fast when mandatory mode is enabled
"""

from __future__ import annotations

import time

from src.ingestion.models import ArticleRecord
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_CHUNK_SIZE = 4500       # Google Translate safe limit per request
_RETRY_DELAY = 2.0       # seconds to wait between retries
_MAX_RETRIES = 2


def _chunk_text(text: str, size: int = _CHUNK_SIZE) -> list[str]:
    """Split *text* into chunks of at most *size* characters, breaking on newlines."""
    if len(text) <= size:
        return [text]
    chunks, current = [], []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) > size and current:
            chunks.append("".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def _translate_text_with_status(text: str, source_lang: str, target_lang: str = "en") -> tuple[str, bool]:
    """
    Translate *text* from *source_lang* to English.
    Returns (translated_text, success).
    """
    if not text or not text.strip():
        return text, True

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        log.warning("deep-translator not installed. Run: pip install deep-translator")
        return text, False

    chunks = _chunk_text(text)
    translated_chunks: list[str] = []
    all_ok = True

    for chunk in chunks:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                translator = GoogleTranslator(source=source_lang, target=target_lang)
                result = translator.translate(chunk)
                translated_chunks.append(result or chunk)
                break
            except Exception as exc:
                if attempt == _MAX_RETRIES:
                    log.warning(
                        "Translation failed after %d attempts: %s — keeping original",
                        _MAX_RETRIES, exc,
                    )
                    translated_chunks.append(chunk)
                    all_ok = False
                else:
                    time.sleep(_RETRY_DELAY)

    return "\n".join(translated_chunks), all_ok


def _translate_text(text: str, source_lang: str) -> str:
    """Backward-compatible helper used by tests and call sites."""
    translated, _ = _translate_text_with_status(text, source_lang, target_lang="en")
    return translated


class Translator:
    """
    Translates ArticleRecord title + content_clean to English in place.

    Languages that are already English are skipped.
    After successful translation, article.language is set to target language.
    """

    # Map langdetect codes → deep-translator / Google codes where they differ
    _LANG_MAP: dict[str, str] = {
        "zh-cn": "zh-CN",
        "zh-tw": "zh-TW",
        "zh":    "zh-CN",
    }

    def __init__(self) -> None:
        self._enabled: bool = settings("ingestion.translate_to_english", True)
        self._translate_unknown: bool = settings(
            "ingestion.translate_unknown_to_english", True
        )
        self._target_lang: str = settings("ingestion.translation_target_language", "en")
        self._require_success: bool = settings("ingestion.require_translation_success", True)

    def translate(self, article: ArticleRecord) -> ArticleRecord:
        """
        Translate *article* in place. Returns the same object.

        Skips if:
          - translation is disabled in settings
          - language is "en" or empty
        """
        if not self._enabled:
            return article

        lang = article.language or "unknown"

        if lang in ("en", ""):
            return article

        if lang == "unknown":
            if not self._translate_unknown:
                return article
            source = "auto"
        else:
            # Normalise language code for Google Translate
            source = self._LANG_MAP.get(lang, lang)

        log.info(
            "Translating article [%s → %s]: %s",
            source,
            self._target_lang,
            article.url[:70],
        )

        translated_ok = True
        translated_any = False

        if article.title:
            translated_any = True
            article.title, title_ok = _translate_text_with_status(
                article.title, source, target_lang=self._target_lang
            )
            translated_ok = translated_ok and title_ok

        if article.content_clean:
            translated_any = True
            article.content_clean, content_ok = _translate_text_with_status(
                article.content_clean, source, target_lang=self._target_lang
            )
            translated_ok = translated_ok and content_ok

        if translated_any and not translated_ok:
            article.relevance_reason = (
                article.relevance_reason + f"|translation_failed_from_{lang}"
                if article.relevance_reason
                else f"translation_failed_from_{lang}"
            )
            if self._require_success:
                raise RuntimeError(
                    f"Mandatory translation failed for source language '{lang}'."
                )
            return article

        # Normalise language to the project-wide common language.
        article.language = self._target_lang

        # Mark as translated; keep original language code
        article.relevance_reason = (
            article.relevance_reason + f"|translated_from_{lang}"
            if article.relevance_reason
            else f"translated_from_{lang}"
        )

        return article