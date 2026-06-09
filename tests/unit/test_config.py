"""Unit tests for src.utils.config."""

import pytest
from pathlib import Path


def test_settings_callable():
    from src.utils.config import settings
    assert settings("project.name") == "temporal_kg"


def test_settings_default():
    from src.utils.config import settings
    assert settings("nonexistent.key", "fallback") == "fallback"


def test_settings_abs_path():
    from src.utils.config import settings
    p = settings.abs_path("paths.db")
    assert isinstance(p, Path)
    assert p.name.endswith(".sqlite")


def test_settings_project_root_exists():
    from src.utils.config import settings
    assert settings.project_root.exists()
