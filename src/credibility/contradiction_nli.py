# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.credibility.contradiction_nli
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Natural-language-inference contradiction detection between claim sentences.

``CorroborationAnalyzer`` previously flagged a group of claims as
"contradictory" purely structurally: only if the extraction pipeline had
tagged members of the *same exact or semantically-merged signature group*
with more than one ``event_type`` or more than one date window (see
``_summarize`` in ``corroboration.py``). That check is blind to the case
that actually matters for fake-news detection: two articles can land in the
same group -- same event type, same date, near-identical surrounding text,
correctly merged as "about the same event" -- while asserting incompatible
facts within it ("12 people were injured" vs. "2 people were injured", or
"the deal was signed" vs. "the deal collapsed"). Structurally these look
identical; only the sentence content actually disagrees.

This module runs a pretrained NLI (natural language inference) model over
pairs of claim sentences within a group and flags a semantic contradiction
when the model's contradiction probability (checked in both directions,
since NLI premise/hypothesis order matters) crosses a threshold. See
``evaluate_contradiction.py`` for the precision/recall of this detector
against a hand-labeled pair set before trusting its default threshold.

Guarded/lazy import, same pattern as ``SemanticSimilarityScorer``: if
``transformers``/``torch`` or the model weights are unavailable, callers
fall back to the structural-only contradiction flag.
"""

from __future__ import annotations

from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-xsmall"
DEFAULT_THRESHOLD = 0.5


class ContradictionDetector:
    """Lazy-loaded pairwise NLI contradiction classifier."""

    def __init__(self) -> None:
        self._model_name = settings(
            "credibility.contradiction_nli.model", DEFAULT_MODEL
        )
        self._enabled = bool(settings("credibility.contradiction_nli.enabled", True))
        self.threshold = float(
            settings("credibility.contradiction_nli.threshold", DEFAULT_THRESHOLD)
        )
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._contradiction_index: int | None = None
        self._entailment_index: int | None = None
        self._load_attempted = False

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        if not self._enabled:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._torch = torch
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self._model_name
            )
            self._model.eval()
            self._contradiction_index = self._find_label_index("contradiction")
            self._entailment_index = self._find_label_index("entailment")
            if self._contradiction_index is None or self._entailment_index is None:
                raise ValueError(
                    f"Model {self._model_name} is missing 'contradiction' or "
                    f"'entailment' in id2label: {self._model.config.id2label}"
                )
        except Exception as exc:  # pragma: no cover - environment dependent
            log.warning(
                "Contradiction NLI model unavailable (%s); falling back to "
                "structural-only contradiction detection.",
                exc,
            )
            self._tokenizer = None
            self._model = None

    def _find_label_index(self, needle: str) -> int | None:
        for index, label in self._model.config.id2label.items():
            if needle.lower() in str(label).lower():
                return int(index)
        return None

    def available(self) -> bool:
        self._load()
        return self._model is not None

    def contradiction_score(self, sentence_a: str, sentence_b: str) -> float:
        """Return the max contradiction probability across both NLI directions.

        NLI is directional (premise -> hypothesis), and which sentence is
        "the premise" between two independently-reported claims is
        arbitrary, so this checks both orderings and takes the stronger
        signal -- a symmetric contradiction score.
        """
        self._load()
        if not self.available():
            return 0.0
        torch = self._torch
        try:
            with torch.no_grad():
                encoded = self._tokenizer(
                    [sentence_a, sentence_b],
                    [sentence_b, sentence_a],
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors="pt",
                )
                logits = self._model(**encoded).logits
                probs = torch.nn.functional.softmax(logits, dim=1)
                contradiction_probs = probs[:, self._contradiction_index]
                return float(contradiction_probs.max().item())
        except Exception as exc:  # pragma: no cover - environment dependent
            log.warning("NLI scoring failed (%s); treating pair as non-contradictory.", exc)
            return 0.0

    def is_contradiction(self, sentence_a: str, sentence_b: str) -> bool:
        return self.contradiction_score(sentence_a, sentence_b) >= self.threshold

    def entailment_score(self, premise: str, hypothesis: str) -> float:
        """Return P(entailment) for a fixed premise -> hypothesis direction.

        Unlike ``contradiction_score``, this is *not* symmetric: premise and
        hypothesis play different, fixed roles (used for zero-shot
        classification -- does the claim sentence entail a specific
        candidate state description?), so callers must pass them in the
        intended order rather than relying on a max-over-both-directions.
        """
        self._load()
        if not self.available():
            return 0.0
        torch = self._torch
        try:
            with torch.no_grad():
                encoded = self._tokenizer(
                    [premise],
                    [hypothesis],
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors="pt",
                )
                logits = self._model(**encoded).logits
                probs = torch.nn.functional.softmax(logits, dim=1)
                return float(probs[0, self._entailment_index].item())
        except Exception as exc:  # pragma: no cover - environment dependent
            log.warning("NLI entailment scoring failed (%s); returning 0.0.", exc)
            return 0.0
