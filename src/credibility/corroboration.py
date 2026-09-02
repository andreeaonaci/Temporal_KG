# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Transparent corroboration heuristics for event and claim support."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.credibility.contradiction_nli import ContradictionDetector
from src.credibility.publisher_networks import resolve_publisher
from src.credibility.scorer import CredibilityScorer
from src.credibility.semantic_similarity import SemanticSimilarityScorer
from src.extraction.pipeline_utils import (
    build_claim_signature,
    build_event_signature,
    load_json_by_article,
)
from src.graph.graph_loader import KnowledgeGraphLoader
from src.temporal.lifecycle import LifecycleStateClassifier, verify_sequence
from src.temporal.reasoner import compare_ranges
from src.utils.config import settings

# Allen relations meaning "these two intervals don't share any point in
# time" -- i.e. one strictly precedes or touches the other. An NLI
# contradiction between two claims whose event dates fall in one of these
# relations is evidence of *claim evolution* (a lifecycle transition:
# proposed -> signed -> rejected), not a genuine contradiction, since the
# two reports aren't describing the same instant. Everything else --
# equals/overlaps/during/contains/starts/finishes and their inverses --
# means the claims share time, so an NLI contradiction between them is a
# real disagreement about the same fact.
_TEMPORALLY_SEQUENTIAL_RELATIONS = frozenset({"before", "after", "meets", "met_by"})


@dataclass
class EvidenceRecord:
    """Compact evidence for one article-backed event."""

    article_id: str
    event_id: str
    record_type: str
    record_id: str
    record_key: str
    event_type: str
    sentence: str
    source_name: str | None
    source_domain: str | None
    url: str | None
    published_at: str | None
    start_date: str | None
    end_date: str | None


class CorroborationAnalyzer:
    """Aggregate article-level event evidence into support summaries."""

    def __init__(
        self,
        scorer: CredibilityScorer | None = None,
        semantic_scorer: SemanticSimilarityScorer | None = None,
        contradiction_detector: ContradictionDetector | None = None,
        lifecycle_classifier: LifecycleStateClassifier | None = None,
    ) -> None:
        self._scorer = scorer or CredibilityScorer()
        self._semantic = semantic_scorer or SemanticSimilarityScorer()
        self._use_semantic_merge = bool(
            settings("credibility.semantic_similarity.merge_corroboration", True)
        )
        self._contradiction_detector = contradiction_detector or ContradictionDetector()
        self._use_nli_contradiction = bool(
            settings("credibility.contradiction_nli.enabled", True)
        )
        self._min_contradiction_relevance = float(
            settings("credibility.contradiction_nli.min_relevance_similarity", 0.15)
        )
        self._use_temporal_gate = bool(
            settings("credibility.contradiction_nli.temporal_gate", True)
        )
        self._lifecycle_classifier = lifecycle_classifier or LifecycleStateClassifier(
            self._contradiction_detector
        )
        self._use_lifecycle_verification = bool(
            settings("credibility.contradiction_nli.lifecycle_verification", True)
        )

    def analyze_directories(
        self,
        *,
        entities_dir: Path,
        temporals_dir: Path,
        events_dir: Path,
    ) -> dict[str, list[dict[str, Any]]]:
        entity_payloads = load_json_by_article(entities_dir)
        temporal_payloads = load_json_by_article(temporals_dir)
        event_payloads = load_json_by_article(events_dir)

        evidences: list[EvidenceRecord] = []
        for article_id, event_payload in sorted(event_payloads.items()):
            source_article = (
                event_payload.get("source_article")
                or entity_payloads.get(article_id, {}).get("source_article")
                or temporal_payloads.get(article_id, {}).get("source_article")
                or {}
            )
            temporal_map = {
                item["temporal_id"]: KnowledgeGraphLoader._temporal_record(
                    item,
                    article_id,
                )
                for item in temporal_payloads.get(article_id, {}).get(
                    "temporal_expressions",
                    [],
                )
            }
            for event in event_payload.get("events", []):
                temporal = temporal_map.get(event.get("temporal_id"))
                event_key = build_event_signature(
                    event,
                    temporal,
                    start_date=(
                        temporal.get("start_date") if temporal else None
                    ),
                    end_date=(
                        temporal.get("end_date") if temporal else None
                    ),
                )
                claim_key = build_claim_signature(
                    event.get("sentence", ""),
                    event_type=event.get("event_type"),
                    event_signature=event_key,
                )
                evidence = self._build_evidence(
                    article_id=article_id,
                    event=event,
                    source_article=source_article,
                    temporal=temporal,
                    record_type="event",
                    record_id=event["event_id"],
                    record_key=event_key,
                )
                evidences.append(evidence)
                evidences.append(
                    self._build_evidence(
                        article_id=article_id,
                        event=event,
                        source_article=source_article,
                        temporal=temporal,
                        record_type="claim",
                        record_id=f"{event['event_id']}:claim",
                        record_key=claim_key,
                    )
                )

        return {
            "events": self._summarize(
                [item for item in evidences if item.record_type == "event"]
            ),
            "claims": self._summarize(
                [item for item in evidences if item.record_type == "claim"]
            ),
        }

    def write_results(
        self,
        results: dict[str, list[dict[str, Any]]],
        *,
        output_dir: Path,
        stem: str = "corroboration",
    ) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for key, rows in results.items():
            json_path = output_dir / f"{stem}.{key}.json"
            csv_path = output_dir / f"{stem}.{key}.csv"
            json_path.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=sorted(rows[0]) if rows else [],
                )
                if rows:
                    writer.writeheader()
                    writer.writerows(rows)
            paths[f"{key}_json"] = json_path
            paths[f"{key}_csv"] = csv_path
        return paths

    def _build_evidence(
        self,
        *,
        article_id: str,
        event: dict[str, Any],
        source_article: dict[str, Any],
        temporal: dict[str, Any] | None,
        record_type: str,
        record_id: str,
        record_key: str,
    ) -> EvidenceRecord:
        url = source_article.get("url")
        return EvidenceRecord(
            article_id=article_id,
            event_id=event["event_id"],
            record_type=record_type,
            record_id=record_id,
            record_key=record_key,
            event_type=event["event_type"],
            sentence=event.get("sentence", ""),
            source_name=source_article.get("source_name"),
            source_domain=self._source_domain(url),
            url=url,
            published_at=source_article.get("published_at"),
            start_date=temporal.get("start_date") if temporal else None,
            end_date=temporal.get("end_date") if temporal else None,
        )

    def _summarize(
        self,
        evidences: list[EvidenceRecord],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[EvidenceRecord]] = {}
        for evidence in evidences:
            grouped.setdefault(evidence.record_key, []).append(evidence)

        merged_from: dict[str, list[str]] = {}
        if self._use_semantic_merge and len(grouped) > 1:
            grouped, merged_from = self._merge_semantic_groups(grouped)

        rows: list[dict[str, Any]] = []
        for record_key, items in sorted(grouped.items()):
            source_domains = sorted(
                {item.source_domain for item in items if item.source_domain}
            )
            publisher_networks = sorted(
                {
                    resolve_publisher(item.source_domain)
                    for item in items
                    if item.source_domain
                }
            )
            article_ids = sorted({item.article_id for item in items})
            event_types = sorted(
                {item.event_type for item in items if item.event_type}
            )
            time_windows = sorted(
                {
                    f"{item.start_date or ''}|{item.end_date or ''}"
                    for item in items
                    if item.start_date or item.end_date
                }
            )
            # NOTE: date-window diversity alone used to also mark a group
            # "structurally contradictory" (len(time_windows) > 1). That
            # signal is now handled by the temporal-gated semantic check
            # below instead, which is strictly more precise: it can only
            # ever fire when a group's members actually disagree in
            # content (NLI-contradiction) *and* their dates are
            # temporally coincident -- vs. the blunt date-string-diversity
            # check, which would equally (mis)fire on legitimate claim
            # evolution (sequential dates, same underlying process) or
            # even two sources agreeing but reporting different date
            # granularity, neither of which is a real contradiction.
            structural_contradiction = len(event_types) > 1
            semantic_contradiction, claim_evolution = self._detect_semantic_contradiction(
                items
            )
            lifecycle_violation = False
            lifecycle_states: list[tuple[str | None, str | None]] = []
            if claim_evolution and self._use_lifecycle_verification:
                # The pairwise gate only knows "these two dates are
                # sequential" -- it can't tell a legitimate lifecycle
                # transition (proposed -> signed) from an impossible one
                # (ratified appearing chronologically *before* signed),
                # since both look identical to it: sequential dates + NLI
                # disagreement. Classify the whole group's claims into
                # lifecycle states and check the full date-ordered sequence
                # against the event type's transition graph before trusting
                # "evolution" as the final answer.
                event_type = items[0].event_type
                dated_states = [
                    (
                        self._lifecycle_classifier.classify(item.sentence, event_type),
                        item.start_date or item.end_date,
                    )
                    for item in items
                ]
                verification = verify_sequence(event_type, dated_states)
                lifecycle_states = verification.state_sequence
                if not verification.valid:
                    lifecycle_violation = True
                    claim_evolution = False
            semantic_contradiction = semantic_contradiction or lifecycle_violation
            contradiction_flag = structural_contradiction or semantic_contradiction
            support_count = len(article_ids)
            # Counts distinct publisher NETWORKS, not raw domains -- a wire
            # story mirrored across a state broadcaster's five language
            # editions is one independent verification, not five. See
            # src/credibility/publisher_networks.py.
            source_diversity = len(publisher_networks)
            repeated_reporting = support_count > 1 and source_diversity > 1
            isolated_claim = support_count == 1 or source_diversity <= 1
            credibility_score = self._credibility_score(
                items,
                support_count=support_count,
                source_diversity=source_diversity,
                contradiction_flag=contradiction_flag,
            )
            rows.append(
                {
                    "record_type": items[0].record_type,
                    "record_key": record_key,
                    "representative_id": items[0].record_id,
                    "event_ids": sorted({item.event_id for item in items}),
                    "article_ids": article_ids,
                    "event_types": event_types,
                    "support_count": support_count,
                    "source_diversity": source_diversity,
                    "source_domains": source_domains,
                    "publisher_networks": publisher_networks,
                    "repeated_reporting": repeated_reporting,
                    "isolated_claim": isolated_claim,
                    "contradiction_flag": contradiction_flag,
                    "structural_contradiction_flag": structural_contradiction,
                    "semantic_contradiction_flag": semantic_contradiction,
                    "claim_evolution_flag": claim_evolution,
                    "lifecycle_violation_flag": lifecycle_violation,
                    "lifecycle_states": lifecycle_states,
                    "semantically_merged_keys": merged_from.get(record_key, []),
                    "time_windows": time_windows,
                    "credibility_score": round(credibility_score, 3),
                    "verification_status": self._verification_status(
                        support_count=support_count,
                        source_diversity=source_diversity,
                        contradiction_flag=contradiction_flag,
                    ),
                    "sample_sentence": items[0].sentence,
                    "sample_sentences": sorted({item.sentence for item in items if item.sentence}),
                }
            )
        return rows

    def _detect_semantic_contradiction(
        self, items: list[EvidenceRecord]
    ) -> tuple[bool, bool]:
        """Check pairwise NLI contradiction between distinct sentences in a group.

        Returns ``(is_contradiction, is_claim_evolution)``.

        The structural flag can't see this case: items land in the same
        group (same exact signature, or merged as semantically similar)
        precisely because they're about the same event -- so their
        event_type/date always match by construction. Only the sentence
        content can reveal that two "corroborating" reports actually
        disagree (different casualty counts, "signed" vs. "collapsed").

        Gated by a cheap embedding-similarity pre-filter before the NLI
        call: NLI models trained on MNLI-style data rarely see genuinely
        off-topic hypothesis pairs, so "neutral" in practice tends to mean
        "same topic, unconfirmed" rather than "unrelated" -- two sentences
        about completely different things can get miscoded as
        "contradiction" rather than the "neutral" a human would pick (see
        evaluate_contradiction.py's contra_009 case).

        A second, temporal gate then distinguishes a genuine contradiction
        from claim evolution: two reports disagreeing about "the deal was
        proposed" vs. "the deal was signed" aren't contradicting each
        other if their extracted event dates are different points in the
        claim's lifecycle (an Allen "before"/"after"/"meets"/"met_by"
        relation) -- they're describing sequential stages of the same
        real-world process. An NLI disagreement only counts as a true
        contradiction when the two events' time windows actually coincide
        (any other Allen relation: equals/overlaps/during/contains/
        starts/finishes and their inverses), since only then are both
        reports describing the same instant. Falls back to treating any
        NLI disagreement as a contradiction when either date is unresolved
        -- there's no temporal evidence to reclassify it as evolution.
        """
        if not self._use_nli_contradiction or not self._contradiction_detector.available():
            return False, False
        distinct: dict[str, EvidenceRecord] = {}
        for item in items:
            if item.sentence:
                distinct.setdefault(item.sentence, item)
        sentences = sorted(distinct)
        if len(sentences) < 2:
            return False, False
        embeddings = (
            self._semantic.embed_many(sentences) if self._semantic.available() else None
        )
        found_contradiction = False
        found_evolution = False
        for i in range(len(sentences)):
            for j in range(i + 1, len(sentences)):
                if embeddings is not None:
                    relevance = self._semantic.cosine_similarity(
                        embeddings[i], embeddings[j]
                    )
                    if relevance < self._min_contradiction_relevance:
                        continue
                if not self._contradiction_detector.is_contradiction(
                    sentences[i], sentences[j]
                ):
                    continue

                if not self._use_temporal_gate:
                    found_contradiction = True
                    continue

                left, right = distinct[sentences[i]], distinct[sentences[j]]
                relation = compare_ranges(
                    left.start_date, left.end_date, right.start_date, right.end_date
                )
                if relation in _TEMPORALLY_SEQUENTIAL_RELATIONS:
                    found_evolution = True
                else:
                    # "unknown" (missing dates) and every temporally-coincident
                    # relation both fall through here -- no temporal evidence
                    # to justify reclassifying as evolution either way.
                    found_contradiction = True
        return found_contradiction, found_evolution and not found_contradiction

    def _merge_semantic_groups(
        self,
        grouped: dict[str, list[EvidenceRecord]],
    ) -> tuple[dict[str, list[EvidenceRecord]], dict[str, list[str]]]:
        """Merge exact-signature groups whose representative sentences are
        near-duplicates into one corroboration group.

        Bounded to comparisons within the same ``event_type`` so unrelated
        claim types never merge on generic phrasing overlap alone, and so
        the pairwise comparison stays cheap (O(bucket_size^2) per type,
        not O(n^2) over the whole corpus). Falls back to a no-op (returns
        *grouped* unchanged) if the embedding model isn't available --
        exact-signature matching still runs either way.
        """
        if not self._semantic.available():
            return grouped, {}

        keys = list(grouped.keys())
        representative_sentence = {key: grouped[key][0].sentence for key in keys}
        representative_type = {key: grouped[key][0].event_type for key in keys}

        buckets: dict[str, list[str]] = {}
        for key in keys:
            buckets.setdefault(representative_type[key], []).append(key)

        parent = {key: key for key in keys}

        def find(node: str) -> str:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(a: str, b: str) -> None:
            root_a, root_b = find(a), find(b)
            if root_a != root_b:
                # Deterministic tie-break: output doesn't depend on dict order.
                parent[max(root_a, root_b)] = min(root_a, root_b)

        for bucket_keys in buckets.values():
            if len(bucket_keys) < 2:
                continue
            sentences = [representative_sentence[key] for key in bucket_keys]
            embeddings = self._semantic.embed_many(sentences)
            for i in range(len(bucket_keys)):
                if embeddings[i] is None:
                    continue
                for j in range(i + 1, len(bucket_keys)):
                    if embeddings[j] is None:
                        continue
                    if self._semantic.is_match(embeddings[i], embeddings[j]):
                        union(bucket_keys[i], bucket_keys[j])

        components: dict[str, list[str]] = {}
        for key in keys:
            components.setdefault(find(key), []).append(key)

        merged_grouped: dict[str, list[EvidenceRecord]] = {}
        merged_from: dict[str, list[str]] = {}
        for canonical, member_keys in components.items():
            combined: list[EvidenceRecord] = []
            for member_key in sorted(member_keys):
                combined.extend(grouped[member_key])
            merged_grouped[canonical] = combined
            if len(member_keys) > 1:
                merged_from[canonical] = sorted(member_keys)

        return merged_grouped, merged_from

    def _credibility_score(
        self,
        items: list[EvidenceRecord],
        *,
        support_count: int,
        source_diversity: int,
        contradiction_flag: bool,
    ) -> float:
        domain_scores = [
            self._scorer.score_url(item.url or "")
            for item in items
            if item.url
        ]
        base_score = (
            sum(domain_scores) / len(domain_scores)
            if domain_scores
            else self._scorer._default
        )
        support_bonus = min(0.3, (support_count - 1) * 0.08)
        diversity_bonus = min(0.15, max(0, source_diversity - 1) * 0.05)
        contradiction_penalty = 0.35 if contradiction_flag else 0.0
        final_score = (
            base_score
            + support_bonus
            + diversity_bonus
            - contradiction_penalty
        )
        return max(0.0, min(1.0, final_score))

    @staticmethod
    def _verification_status(
        *,
        support_count: int,
        source_diversity: int,
        contradiction_flag: bool,
    ) -> str:
        if contradiction_flag:
            return "contradictory"
        if support_count >= 3 and source_diversity >= 2:
            return "corroborated"
        if support_count >= 2:
            return "weakly_supported"
        return "unresolved"

    @staticmethod
    def _source_domain(url: str | None) -> str | None:
        if not url:
            return None
        return urlparse(url).netloc.lower().lstrip("www.")
