#!/usr/bin/env python3
# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Mine a large, real pairwise pool for the semantic-corroboration-matching
ablation, spanning the full similarity spectrum -- not just the pairs the
merge algorithm actually combined (mine_real_candidate_pairs.py only mines
already-merged pairs, i.e. positives only). This script instead reproduces
the pre-merge exact-signature grouping directly, buckets representative
sentences by event_type (same bucketing rule the real merge step uses), and
computes ALL pairwise cosine similarities within each bucket -- giving both
high-similarity (likely-positive) and low-similarity (likely-negative) real
pairs for a properly balanced, much-larger-than-10 gold set.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.credibility.semantic_similarity import SemanticSimilarityScorer  # noqa: E402
from src.extraction.pipeline_utils import (  # noqa: E402
    build_claim_signature,
    build_event_signature,
    load_json_by_article,
    stable_id,
)
from src.graph.graph_loader import KnowledgeGraphLoader  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities-dir", type=Path, default=Path("data/exports/entities"))
    parser.add_argument("--temporals-dir", type=Path, default=Path("data/exports/temporals"))
    parser.add_argument("--events-dir", type=Path, default=Path("data/exports/events"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-per-bucket", type=int, default=400,
                         help="Cap pairwise comparisons per event_type bucket (avoid O(n^2) blowup).")
    args = parser.parse_args()

    entity_payloads = load_json_by_article(args.entities_dir)
    temporal_payloads = load_json_by_article(args.temporals_dir)
    event_payloads = load_json_by_article(args.events_dir)

    # Reproduce exact-signature grouping: record_key -> set of distinct sentences, event_type
    groups: dict[str, dict] = {}
    for article_id, event_payload in sorted(event_payloads.items()):
        temporal_map = {
            item["temporal_id"]: KnowledgeGraphLoader._temporal_record(item, article_id)
            for item in temporal_payloads.get(article_id, {}).get("temporal_expressions", [])
        }
        for event in event_payload.get("events", []):
            temporal = temporal_map.get(event.get("temporal_id"))
            event_key = build_event_signature(
                event, temporal,
                start_date=temporal.get("start_date") if temporal else None,
                end_date=temporal.get("end_date") if temporal else None,
            )
            claim_key = build_claim_signature(
                event.get("sentence", ""), event_type=event.get("event_type"), event_signature=event_key,
            )
            g = groups.setdefault(claim_key, {"event_type": event.get("event_type"), "sentences": set()})
            if event.get("sentence"):
                g["sentences"].add(event["sentence"])

    # Bucket DISTINCT representative sentences by event_type (one per exact-signature group,
    # same as corroboration.py's _merge_semantic_groups uses items[0].sentence)
    buckets: dict[str, list[str]] = {}
    for g in groups.values():
        if not g["sentences"]:
            continue
        rep = sorted(g["sentences"])[0]
        buckets.setdefault(g["event_type"], []).append(rep)

    scorer = SemanticSimilarityScorer()
    print(f"model available: {scorer.available()}  threshold: {scorer.threshold}")

    pairs = []
    seen = set()
    for event_type, sentences in buckets.items():
        sentences = sorted(set(sentences))
        if len(sentences) < 2:
            continue
        embeddings = scorer.embed_many(sentences)
        combos = list(itertools.combinations(range(len(sentences)), 2))
        if len(combos) > args.max_per_bucket:
            # Deterministic spread: stride-sample across the combination list
            step = len(combos) / args.max_per_bucket
            combos = [combos[int(i * step)] for i in range(args.max_per_bucket)]
        for i, j in combos:
            if embeddings[i] is None or embeddings[j] is None:
                continue
            a, b = sentences[i], sentences[j]
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            sim = scorer.cosine_similarity(embeddings[i], embeddings[j])
            pairs.append({
                "id": stable_id("semantic_ablation", event_type, a, b),
                "event_type": event_type,
                "sentence_a": a[:500],
                "sentence_b": b[:500],
                "similarity": sim,
                "predicted_merge": sim >= scorer.threshold,
            })

    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    print(f"Mined {len(pairs)} real pairwise comparisons across {len(buckets)} event-type buckets.")
    n_pos_pred = sum(1 for p in pairs if p["predicted_merge"])
    print(f"  {n_pos_pred} predicted-merge (sim >= {scorer.threshold}), {len(pairs) - n_pos_pred} predicted-no-merge")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
