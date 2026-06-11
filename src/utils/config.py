# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.utils.config
~~~~~~~~~~~~~~~~~~~~~~~~
Loads configuration from config/settings.yaml, then overlays any
TEMPORAL_KG_<SECTION>_<KEY> environment variables (and .env file).

Usage
-----
    from src.utils.config import settings

    db_path = settings("paths.db")
    log_level = settings("logging.level")
"""

from __future__ import annotations

import os
import re
from functools import reduce
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# ── Locate project root (two levels up from this file) ──────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_FILE = _PROJECT_ROOT / "config" / "settings.yaml"
_ENV_FILE = _PROJECT_ROOT / "config" / ".env"

# Load .env if it exists (override=True to ensure .env takes precedence over system env)
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)
else:
    load_dotenv(_PROJECT_ROOT / ".env", override=True)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _nested_set(d: dict, keys: list[str], value: Any) -> None:
    """Set a value deep inside a nested dict, creating intermediate dicts."""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def _apply_env_overrides(cfg: dict) -> dict:
    """
    Scan environment for TEMPORAL_KG_<SECTION>_<KEY> variables and
    overlay them onto *cfg* (mutates in place, also returns cfg).
    """
    prefix = "TEMPORAL_KG_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        # TEMPORAL_KG_DATABASE_NEO4J_URI → ["database", "neo4j_uri"]
        # Split only on the first underscore to get section + key
        remainder = env_key[len(prefix):]
        parts = remainder.split("_", 1)
        path_parts = [p.lower() for p in parts]
        _nested_set(cfg, path_parts, env_val)
    return cfg


def _get_nested(cfg: dict, dotted_key: str, default: Any = None) -> Any:
    """Retrieve a dotted key like 'paths.db' from a nested dict."""
    try:
        return reduce(lambda d, k: d[k], dotted_key.split("."), cfg)
    except (KeyError, TypeError):
        return default


class _Settings:
    """
    Thin wrapper around the merged YAML + env config dict.

    Examples
    --------
    >>> from src.utils.config import settings
    >>> settings("project.name")
    'temporal_kg'
    >>> settings("paths.db")
    'db/temporal_kg.sqlite'
    """

    def __init__(self) -> None:
        self._cfg = _apply_env_overrides(_load_yaml(_CONFIG_FILE))
        self._root = _PROJECT_ROOT

    # Make the object callable: settings("section.key")
    def __call__(self, key: str, default: Any = None) -> Any:
        return _get_nested(self._cfg, key, default)

    def get(self, key: str, default: Any = None) -> Any:
        return self(key, default)

    def as_dict(self) -> dict:
        """Return a shallow copy of the full config dict."""
        return dict(self._cfg)

    @property
    def project_root(self) -> Path:
        return self._root

    def abs_path(self, relative_key: str) -> Path:
        """
        Resolve a config key that holds a relative path against the
        project root.

        Example
        -------
        >>> settings.abs_path("paths.db")
        PosixPath('/home/user/temporal_kg/db/temporal_kg.sqlite')
        """
        rel = self(relative_key)
        if rel is None:
            raise KeyError(f"Config key '{relative_key}' not found.")
        return self._root / rel


# Singleton — import and use directly
settings = _Settings()
