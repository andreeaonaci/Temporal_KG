"""DeepKE command runner for entity/relation extraction."""

from __future__ import annotations

import json
import subprocess
import shlex
from pathlib import Path
from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class DeepKEClient:
    """Run DeepKE using a command template defined in settings."""

    def __init__(self) -> None:
        self._enabled = settings("extraction.deepke.enabled", False)
        self._command_template = settings(
            "extraction.deepke.command_template",
            "python ../../scripts/deepke_runner.py --input {input} --output {output}",
        )
        self._conda_env = settings("extraction.deepke.conda_env", "")
        self._working_dir = settings.abs_path("extraction.deepke.working_dir")
        self._output_dir = settings.abs_path("extraction.deepke.output_dir")
        self._timeout = int(settings("extraction.deepke.timeout_seconds", 600))

    def enabled(self) -> bool:
        return bool(self._enabled)

    def output_path(self, article_id: str) -> Path:
        return self._output_dir / f"{article_id}.json"

    def write_input(self, article: dict[str, Any], input_dir: Path) -> Path:
        input_dir.mkdir(parents=True, exist_ok=True)
        article_id = article.get("article_id") or article.get("url_hash")
        if not article_id:
            raise ValueError("Article id missing for DeepKE input")
        payload = {
            "id": article_id,
            "title": article.get("title") or "",
            "text": article.get("content_clean") or "",
            "url": article.get("url") or "",
            "published_at": article.get("published_at") or "",
        }
        target = input_dir / f"{article_id}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def run(self, input_path: Path, output_path: Path) -> bool:
        if not self._enabled:
            return False
        self._output_dir.mkdir(parents=True, exist_ok=True)
        command_text = self._command_template.format(
            input=str(input_path),
            output=str(output_path),
        )
        command = shlex.split(command_text)
        if self._conda_env:
            command = ["conda", "run", "-n", self._conda_env, *command]
        try:
            subprocess.run(
                command,
                cwd=str(self._working_dir),
                shell=False,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self._timeout,
            )
            return output_path.exists()
        except subprocess.TimeoutExpired:
            log.error("DeepKE timed out for %s", input_path)
            return False
        except subprocess.CalledProcessError as exc:
            log.error("DeepKE failed: %s", exc.stderr.decode("utf-8", "ignore"))
            return False
