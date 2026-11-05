# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

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

import threading
import time

from src.ingestion.models import ArticleRecord
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_CHUNK_SIZE = 4500       # Google Translate safe limit per request
_RETRY_DELAY = 2.0       # seconds to wait between retries
_MAX_RETRIES = 2

# deep-translator's GoogleTranslator sometimes does not raise on failure --
# it returns Google's HTML error page's own text as if it were a successful
# translation. Confirmed 2026-08-25: at request volumes big enough to trip
# Google's free-endpoint rate limiting (real body text translated in bulk
# during a historical backfill, vs. the short titles this previously only
# ever translated), GoogleTranslator('你好') returned the string below
# instead of raising -- which would have been silently written into the
# corpus as if it were a real translation. Never seen at title-only volume,
# only appeared once full-article-text translation (src/ingestion/
# article_scraper.py) made per-run request counts much higher.
_ERROR_PAGE_MARKERS = ("Error 500 (Server Error)", "That's an error", "That’s an error")


def _looks_like_error_page(text: str) -> bool:
    return any(marker in text for marker in _ERROR_PAGE_MARKERS)


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


# Local NLLB-200 (one multilingual model, no network at translate time, no rate
# limit). Languages not listed (and "auto") fall back to the Google path.
_LOCAL_MODEL = "facebook/nllb-200-distilled-600M"
_NLLB_CODES = {
    "zh-CN": "zho_Hans", "zh-TW": "zho_Hant", "ro": "ron_Latn", "bg": "bul_Cyrl",
    "sv": "swe_Latn", "ru": "rus_Cyrl", "da": "dan_Latn", "de": "deu_Latn",
    "fr": "fra_Latn", "es": "spa_Latn", "it": "ita_Latn", "pt": "por_Latn",
    "ar": "arb_Arab", "hu": "hun_Latn", "pl": "pol_Latn", "nl": "nld_Latn",
    "tr": "tur_Latn", "uk": "ukr_Cyrl", "ja": "jpn_Jpan", "ko": "kor_Hang",
    "cs": "ces_Latn", "hr": "hrv_Latn", "vi": "vie_Latn", "id": "ind_Latn", "th": "tha_Thai", "he": "heb_Hebr", "sk": "slk_Latn", "sl": "slv_Latn", "no": "nob_Latn", "ca": "cat_Latn", "lt": "lit_Latn", "lv": "lvs_Latn", "et": "est_Latn", "mk": "mkd_Cyrl", "sq": "als_Latn", "sr": "srp_Cyrl", "el": "ell_Grek", "fi": "fin_Latn",
}
_LOCAL_CHUNK = 400  # chars per piece; keeps each piece well inside the model's context
_local_cache: dict[str, tuple] = {}

# Domain terms the model gets wrong (measured: Cernavoda -> "Chernobyl", Belt and Road ->
# "Belt and Road Bridge"). Substituted in the source text before translation.
# shortcut: hand-picked from a handful of test sentences, extend as errors are found.
_GLOSSARY_ZH = {"切尔纳沃达": "Cernavoda", "一带一路": "Belt and Road Initiative"}


def _split_sentences(text: str, size: int = _LOCAL_CHUNK) -> list[str]:
    """Greedy-pack sentences into pieces of at most *size* chars."""
    import re
    pieces: list[str] = []
    for sent in re.findall(r"[^。！？!?.\n]+[。！？!?.]?", text):
        sent = sent.strip()
        pieces.extend(sent[i:i + size] for i in range(0, len(sent), size))
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > size:
            out.append(cur)
            cur = ""
        cur += p + " "
    return out + ([cur] if cur.strip() else [])


def _translate_local_many(texts: list[str], source_lang: str) -> tuple[list[str], bool]:
    """Translate several texts in one pass: all pieces are pooled, length-sorted
    (little padding) and generated in big batches, then reassembled per text."""
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        dev = "cuda" if torch.cuda.is_available() else "cpu"
        if "m" not in _local_cache:
            model = AutoModelForSeq2SeqLM.from_pretrained(_LOCAL_MODEL, torch_dtype=torch.float16 if dev == "cuda" else torch.float32)
            _local_cache["m"] = (model.eval().to(dev), {})
        model, toks = _local_cache["m"]
        if source_lang not in toks:
            toks[source_lang] = AutoTokenizer.from_pretrained(_LOCAL_MODEL, src_lang=_NLLB_CODES[source_lang])
        tok = toks[source_lang]
        eng = tok.convert_tokens_to_ids("eng_Latn")
        beams = int(settings("ingestion.translation_beams", 1))

        pieces: list[tuple[int, int, str]] = []  # (text index, piece index, piece)
        for ti, text in enumerate(texts):
            if source_lang.startswith("zh"):
                for zh, en in _GLOSSARY_ZH.items():
                    text = text.replace(zh, f" {en} ")
            pieces.extend((ti, pi, p) for pi, p in enumerate(_split_sentences(text)))
        order = sorted(range(len(pieces)), key=lambda i: len(pieces[i][2]), reverse=True)
        result: dict[int, str] = {}
        step = 48 if dev == "cuda" else 4
        for i in range(0, len(order), step):
            idx = order[i:i + step]
            batch = tok([pieces[j][2] for j in idx], return_tensors="pt", padding=True, truncation=True, max_length=512).to(dev)
            # output is rarely much longer than the input; the cap stops runaway loops early
            cap = min(512, int(batch["input_ids"].shape[1] * 1.6) + 16)
            with torch.no_grad():
                gen = model.generate(**batch, forced_bos_token_id=eng, num_beams=beams, max_new_tokens=cap, no_repeat_ngram_size=3)
            for j, t in zip(idx, tok.batch_decode(gen, skip_special_tokens=True)):
                result[j] = t
        out = [[] for _ in texts]
        for j, (ti, _pi, _p) in sorted(enumerate(pieces), key=lambda x: (x[1][0], x[1][1])):
            out[ti].append(result[j])
        return [" ".join(o) for o in out], True
    except Exception as exc:
        log.warning("Local translation failed (%s: %s) — keeping original", type(exc).__name__, exc)
        return list(texts), False


def _translate_local(text: str, source_lang: str) -> tuple[str, bool]:
    out, ok = _translate_local_many([text], source_lang)
    return out[0], ok


_google_lock = threading.Lock()
_google_last = 0.0


def _google_wait() -> None:
    """Global limiter: Google's free endpoint allows 5 requests/second, so space
    every request (retries included) at least translation_rate_limit_delay apart."""
    global _google_last
    gap = float(settings("ingestion.translation_rate_limit_delay", 0.25))
    with _google_lock:
        wait = _google_last + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _google_last = time.monotonic()


def _translate_text_with_status(text: str, source_lang: str, target_lang: str = "en") -> tuple[str, bool]:
    """
    Translate *text* from *source_lang* to English.
    Returns (translated_text, success).
    """
    if not text or not text.strip():
        return text, True

    if (
        settings("ingestion.translation_backend", "google") == "local"
        and target_lang == "en"
        and source_lang in _NLLB_CODES
    ):
        return _translate_local(text, source_lang)

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
                _google_wait()
                translator = GoogleTranslator(source=source_lang, target=target_lang)
                result = translator.translate(chunk)
                if not result or _looks_like_error_page(result):
                    raise RuntimeError(f"translator returned an error page: {result!r:.120}")
                translated_chunks.append(result)
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

        if (
            settings("ingestion.translation_backend", "google") == "local"
            and self._target_lang == "en"
            and source in _NLLB_CODES
            and article.title
            and article.content_clean
        ):
            (article.title, article.content_clean), translated_ok = _translate_local_many(
                [article.title, article.content_clean], source
            )
            translated_any = True
        elif article.title:
            translated_any = True
            article.title, title_ok = _translate_text_with_status(
                article.title, source, target_lang=self._target_lang
            )
            translated_ok = translated_ok and title_ok

        if article.content_clean and not (translated_any and settings("ingestion.translation_backend", "google") == "local" and source in _NLLB_CODES and article.title):
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