# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.utils.db
~~~~~~~~~~~~~~~~~~~~~
A lightweight, reusable SQLite helper built around the standard
`sqlite3` module.  Provides:

* ``DatabaseManager`` — context-manager connection handling,
  query/execute helpers, migration runner, and a WAL-mode setup.
* ``get_db()``       — convenience factory that reads the path from settings.

Usage
-----
    from src.utils.db import get_db

    with get_db() as db:
        rows = db.fetchall("SELECT * FROM articles WHERE country = ?", ("China",))

    # Or as a long-lived object:
    db = get_db()
    db.connect()
    db.execute("INSERT INTO articles (title) VALUES (?)", ("Test",))
    db.close()
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable

from src.utils.logger import get_logger

log = get_logger(__name__)

# Row type alias
Row = dict[str, Any]


class DatabaseManager:
    """
    SQLite connection wrapper with helper methods.

    Parameters
    ----------
    db_path : Path | str
        Absolute or relative path to the .sqlite file.
        The parent directory is created if it does not exist.
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # ── Connection lifecycle ──────────────────────────────────────────────────

    def connect(self) -> "DatabaseManager":
        """Open the connection and configure pragmas."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.db_path),
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._apply_pragmas()
        log.debug("SQLite connected: %s", self.db_path)
        return self

    def close(self) -> None:
        """Commit pending work and close the connection."""
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None
            log.debug("SQLite connection closed.")

    def __enter__(self) -> "DatabaseManager":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

    # ── Pragmas & setup ───────────────────────────────────────────────────────

    def _apply_pragmas(self) -> None:
        """Enable WAL mode and foreign-key enforcement."""
        assert self._conn is not None
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")

    # ── Transaction helpers ───────────────────────────────────────────────────

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn:
            self._conn.rollback()

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Explicit transaction context manager."""
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise

    # ── Query helpers ─────────────────────────────────────────────────────────

    def _cursor(self) -> sqlite3.Cursor:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn.cursor()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        """Execute a single statement; returns the cursor."""
        cur = self._cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql: str, params_seq: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        """Execute a statement for each row in *params_seq*."""
        cur = self._cursor()
        cur.executemany(sql, params_seq)
        return cur

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Row | None:
        """Return the first matching row as a dict, or None."""
        cur = self.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[Row]:
        """Return all matching rows as a list of dicts."""
        cur = self.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def table_exists(self, table_name: str) -> bool:
        """Check whether *table_name* exists in the current database."""
        row = self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return row is not None

    # ── Schema migration ──────────────────────────────────────────────────────

    def run_migrations(self, migrations_dir: Path | str) -> None:
        """
        Apply SQL migration files in lexicographic order.
        Files must be named like ``001_create_articles.sql``.
        Already-applied migrations are tracked in ``schema_migrations``.
        """
        migrations_dir = Path(migrations_dir)
        if not migrations_dir.exists():
            log.warning("Migrations directory not found: %s", migrations_dir)
            return

        self.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        self.commit()

        sql_files = sorted(migrations_dir.glob("*.sql"))
        if not sql_files:
            log.info("No migration files found in %s", migrations_dir)
            return

        for sql_file in sql_files:
            already_applied = self.fetchone(
                "SELECT filename FROM schema_migrations WHERE filename = ?",
                (sql_file.name,),
            )
            if already_applied:
                log.debug("Migration already applied: %s", sql_file.name)
                continue

            log.info("Applying migration: %s", sql_file.name)
            sql_text = sql_file.read_text(encoding="utf-8")
            try:
                with self.transaction():
                    self._conn.executescript(sql_text)  # type: ignore[union-attr]
                    self.execute(
                        "INSERT INTO schema_migrations (filename) VALUES (?)",
                        (sql_file.name,),
                    )
                log.info("Migration applied: %s", sql_file.name)
            except sqlite3.Error as exc:
                log.error("Migration failed (%s): %s", sql_file.name, exc)
                raise


# ── Convenience factory ───────────────────────────────────────────────────────

def get_db() -> DatabaseManager:
    """
    Return a ``DatabaseManager`` pointed at the path from settings.

    The caller is responsible for connecting/closing (or using as a
    context manager).
    """
    from src.utils.config import settings  # late import

    db_path = settings.abs_path("database.sqlite_path")
    return DatabaseManager(db_path)
