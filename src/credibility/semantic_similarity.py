# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.credibility.semantic_similarity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sentence-embedding similarity for corroboration matching.

``CorroborationAnalyzer`` groups article-level claims into support clusters
by an *exact* signature (event type + participants + date, or the fully
normalized sentence text -- see ``pipeline_utils.build_event_signature`` /
``build_claim_signature``). That catches near-duplicate reporting but misses
the common case of two independent outlets covering the same real event in
different words ("Romania and China signed an energy deal" vs. "Bucharest
and Beijing finalized an agreement on energy cooperation"), which never
share an exact signature and are therefore never counted as corroborating
each other.

This module adds a second, similarity-based matching layer on top of the
exact one: claim sentences are embedded (mean-pooled transformer hidden
states -- the standard sentence-embedding recipe, no extra dependency
beyond the ``transformers``/``torch`` already declared in
``environment.yml``) and pairs above a cosine-similarity threshold are
merged into the same corroboration group. See ``evaluate_corroboration.py``
for the precision/recall ablation of exact-only vs. exact+semantic matching
against a hand-labeled pair set.

Guarded/lazy import, same pattern as ``EntityExtractor``'s spaCy loading:
if ``transformers``/``torch`` or the model weights are unavailable (e.g. no
network on first run), ``available()`` returns False and callers fall back
to exact-signature-only matching -- a setup problem, not a crash.
"""

from __future__ import annotations

from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_THRESHOLD = 0.75


class SemanticSimilarityScorer:
    """Lazy-loaded sentence-embedding cosine-similarity scorer."""

    def __init__(self) -> None:
        self._model_name = settings(
            "credibility.semantic_similarity.model", DEFAULT_MODEL
        )
        self._enabled = bool(
            settings("credibility.semantic_similarity.enabled", True)
        )
        self.threshold = float(
            settings("credibility.semantic_similarity.threshold", DEFAULT_THRESHOLD)
        )
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._load_attempted = False

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        if not self._enabled:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            self._torch = torch
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModel.from_pretrained(self._model_name)
            self._model.eval()
        except Exception as exc:  # pragma: no cover - environment dependent
            log.warning(
                "Semantic similarity model unavailable (%s); falling back to "
                "exact-signature-only corroboration matching.",
                exc,
            )
            self._tokenizer = None
            self._model = None

    def available(self) -> bool:
        self._load()
        return self._model is not None

    def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        """Return one mean-pooled embedding per text, or None per-text on failure."""
        self._load()
        if not self.available() or not texts:
            return [None] * len(texts)

        torch = self._torch
        cleaned = [t if t and t.strip() else " " for t in texts]
        try:
            with torch.no_grad():
                encoded = self._tokenizer(
                    cleaned,
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors="pt",
                )
                output = self._model(**encoded)
                token_embeddings = output.last_hidden_state
                attention_mask = encoded["attention_mask"].unsqueeze(-1).float()
                summed = (token_embeddings * attention_mask).sum(dim=1)
                counts = attention_mask.sum(dim=1).clamp(min=1e-9)
                pooled = summed / counts
                normed = torch.nn.functional.normalize(pooled, p=2, dim=1)
                return [row.tolist() for row in normed]
        except Exception as exc:  # pragma: no cover - environment dependent
            log.warning("Embedding batch failed (%s); skipping semantic match.", exc)
            return [None] * len(texts)

    def embed(self, text: str) -> list[float] | None:
        return self.embed_many([text])[0]

    @staticmethod
    def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
        if a is None or b is None:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        # Vectors are already L2-normalized by embed_many(), so dot product
        # *is* cosine similarity -- no need to re-divide by norms.
        return max(-1.0, min(1.0, dot))

    def is_match(self, a: list[float] | None, b: list[float] | None) -> bool:
        return self.cosine_similarity(a, b) >= self.threshold
