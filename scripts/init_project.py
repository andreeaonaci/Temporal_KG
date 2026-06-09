#!/usr/bin/env python3
"""
scripts/init_project.py
~~~~~~~~~~~~~~~~~~~~~~~
Run once to:
  1. Create all required project folders.
  2. Copy config/.env.example → config/.env  (if .env does not yet exist).
  3. Initialise the SQLite database and run all pending migrations.
  4. Download the spaCy language model if not already present.

Usage
-----
    python scripts/init_project.py [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ── Allow imports from project root ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import settings  # noqa: E402
from src.utils.db import get_db        # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

log = get_logger("init_project")

# ── Directories to guarantee exist ───────────────────────────────────────────
REQUIRED_DIRS: list[str] = [
    "data/raw",
    "data/processed",
    "data/exports",
    "db",
    "db/migrations",
    "logs",
    "config",
]

# __init__.py stubs needed so src/* is importable as a package
PACKAGE_INITS: list[str] = [
    "src",
    "src/ingestion",
    "src/extraction",
    "src/temporal",
    "src/graph",
    "src/ontology",
    "src/credibility",
    "src/utils",
    "tests",
    "tests/unit",
    "tests/integration",
]


def create_directories(dry_run: bool = False) -> None:
    log.info("── Creating project directories ──────────────────────────────")
    for rel_dir in REQUIRED_DIRS:
        abs_dir = PROJECT_ROOT / rel_dir
        if not abs_dir.exists():
            log.info("  CREATE  %s", abs_dir)
            if not dry_run:
                abs_dir.mkdir(parents=True, exist_ok=True)
        else:
            log.debug("  EXISTS  %s", abs_dir)


def create_package_inits(dry_run: bool = False) -> None:
    log.info("── Creating package __init__.py files ────────────────────────")
    for rel_pkg in PACKAGE_INITS:
        init_file = PROJECT_ROOT / rel_pkg / "__init__.py"
        if not init_file.exists():
            log.info("  CREATE  %s", init_file)
            if not dry_run:
                init_file.parent.mkdir(parents=True, exist_ok=True)
                init_file.write_text(
                    f'"""temporal_kg.{rel_pkg.replace("/", ".")}"""\n',
                    encoding="utf-8",
                )
        else:
            log.debug("  EXISTS  %s", init_file)


def copy_env_example(dry_run: bool = False) -> None:
    log.info("── Checking .env file ────────────────────────────────────────")
    src = PROJECT_ROOT / "config" / ".env.example"
    dst = PROJECT_ROOT / "config" / ".env"
    if dst.exists():
        log.info("  .env already exists — skipping copy.")
        return
    if not src.exists():
        log.warning("  .env.example not found — skipping.")
        return
    log.info("  Copying .env.example → .env")
    if not dry_run:
        shutil.copy(src, dst)


def init_database(dry_run: bool = False) -> None:
    log.info("── Initialising SQLite database ──────────────────────────────")
    db_path = settings.abs_path("database.sqlite_path")
    log.info("  DB path: %s", db_path)

    migrations_dir = PROJECT_ROOT / "db" / "migrations"

    if dry_run:
        log.info("  [dry-run] Would connect and run migrations from %s", migrations_dir)
        return

    with get_db() as db:
        db.run_migrations(migrations_dir)
        log.info("  Migrations complete.")


def download_spacy_model(dry_run: bool = False) -> None:
    log.info("── Downloading spaCy model ───────────────────────────────────")
    model = settings("extraction.spacy_model", "en_core_web_sm")
    try:
        import spacy  # noqa: F401
        try:
            import importlib
            importlib.import_module(model.replace("-", "_"))
            log.info("  spaCy model '%s' already installed.", model)
            return
        except ModuleNotFoundError:
            pass
    except ImportError:
        log.warning("  spaCy not installed — skipping model download.")
        return

    log.info("  Downloading spaCy model: %s", model)
    if not dry_run:
        result = subprocess.run(
            [sys.executable, "-m", "spacy", "download", model],
            capture_output=False,
        )
        if result.returncode != 0:
            log.error("  spaCy model download failed.")
        else:
            log.info("  spaCy model '%s' downloaded.", model)


def print_summary() -> None:
    print("\n" + "═" * 60)
    print("  temporal_kg — project initialised successfully")
    print("═" * 60)
    print(f"  Root    : {PROJECT_ROOT}")
    print(f"  DB      : {settings.abs_path('database.sqlite_path')}")
    print(f"  Logs    : {settings.abs_path('paths.logs')}")
    print(f"  Config  : {PROJECT_ROOT / 'config' / 'settings.yaml'}")
    print("\n  Next steps:")
    print("    1. Edit config/.env with your credentials")
    print("    2. Run:  python scripts/run_ingestion.py")
    print("═" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise the temporal_kg project.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without making any changes.",
    )
    args = parser.parse_args()

    if args.dry_run:
        log.info("DRY RUN — no changes will be made.\n")

    create_directories(dry_run=args.dry_run)
    create_package_inits(dry_run=args.dry_run)
    copy_env_example(dry_run=args.dry_run)
    init_database(dry_run=args.dry_run)
    download_spacy_model(dry_run=args.dry_run)

    if not args.dry_run:
        print_summary()


if __name__ == "__main__":
    main()
