# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

import json

from src.credibility.corroboration import CorroborationAnalyzer


def test_corroboration_analysis_scores_cross_source_support(tmp_path):
    article_id_1 = "article-1"
    article_id_2 = "article-2"
    entities_dir = tmp_path / "entities"
    temporals_dir = tmp_path / "temporals"
    events_dir = tmp_path / "events"
    for directory in (entities_dir, temporals_dir, events_dir):
        directory.mkdir()

    for article_id, url in [
        (article_id_1, "https://www.reuters.com/world/china/story"),
        (article_id_2, "https://www.bbc.com/news/world"),
    ]:
        (entities_dir / f"{article_id}.entities.json").write_text(
            json.dumps(
                {"article_id": article_id, "entities": [], "mentions": []}
            ),
            encoding="utf-8",
        )
        (temporals_dir / f"{article_id}.temporals.json").write_text(
            json.dumps(
                {
                    "article_id": article_id,
                    "temporal_expressions": [
                        {
                            "temporal_id": "time-1",
                            "text": "May 2025",
                            "kind": "absolute_date",
                            "normalized": "2025-05",
                            "granularity": "month",
                            "resolved": True,
                            "ambiguous": False,
                            "confidence": 0.9,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (events_dir / f"{article_id}.events.json").write_text(
            json.dumps(
                {
                    "article_id": article_id,
                    "source_article": {
                        "url": url,
                        "title": "China and Romania meet",
                        "published_at": "2025-05-04",
                    },
                    "events": [
                        {
                            "event_id": f"event-{article_id}",
                            "event_type": "DiplomaticMeeting",
                            "trigger": "met",
                            "normalized_trigger": "meeting",
                            "sentence": "China met Romania in May 2025.",
                            "confidence": 0.9,
                            "sentence_index": 0,
                            "participant_entity_ids": [
                                "china-id",
                                "romania-id",
                            ],
                            "temporal_id": "time-1",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    results = CorroborationAnalyzer().analyze_directories(
        entities_dir=entities_dir,
        temporals_dir=temporals_dir,
        events_dir=events_dir,
    )

    assert results["events"][0]["support_count"] == 2
    assert results["events"][0]["source_diversity"] == 2
    assert results["events"][0]["verification_status"] == "weakly_supported"
    assert results["events"][0]["credibility_score"] > 0.8
