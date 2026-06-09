"""Load manually annotated gold files for evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.extraction.pipeline_utils import load_json_by_article


class GoldDataLoader:
    """Load article-keyed gold and predicted extraction payloads."""

    def load_directory(self, directory: Path) -> dict[str, dict[str, Any]]:
        return load_json_by_article(directory)

    def load_bundle(
        self,
        *,
        entities_dir: Path,
        temporals_dir: Path,
        events_dir: Path,
        relations_dir: Path,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            "entities": self.load_directory(entities_dir),
            "temporals": self.load_directory(temporals_dir),
            "events": self.load_directory(events_dir),
            "relations": self.load_directory(relations_dir),
        }
