"""Unit tests for src.utils.db.DatabaseManager."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path):
    from src.utils.db import DatabaseManager
    db = DatabaseManager(tmp_path / "test.sqlite")
    db.connect()
    yield db
    db.close()


def test_connect_creates_file(tmp_path):
    from src.utils.db import DatabaseManager
    db_path = tmp_path / "sub" / "test.sqlite"
    db = DatabaseManager(db_path)
    db.connect()
    assert db_path.exists()
    db.close()


def test_execute_and_fetchall(tmp_db):
    tmp_db.execute(
        "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"
    )
    tmp_db.execute("INSERT INTO items (name) VALUES (?)", ("China",))
    tmp_db.execute("INSERT INTO items (name) VALUES (?)", ("Romania",))
    tmp_db.commit()

    rows = tmp_db.fetchall("SELECT name FROM items ORDER BY name")
    assert [r["name"] for r in rows] == ["China", "Romania"]


def test_fetchone_returns_none_when_missing(tmp_db):
    tmp_db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    tmp_db.commit()
    row = tmp_db.fetchone("SELECT * FROM t WHERE id = ?", (999,))
    assert row is None


def test_table_exists(tmp_db):
    assert not tmp_db.table_exists("nonexistent")
    tmp_db.execute("CREATE TABLE exists_test (id INTEGER PRIMARY KEY)")
    tmp_db.commit()
    assert tmp_db.table_exists("exists_test")


def test_run_migrations(tmp_db, tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_test.sql").write_text(
        "CREATE TABLE migrated (id INTEGER PRIMARY KEY);"
    )
    tmp_db.run_migrations(mig_dir)
    assert tmp_db.table_exists("migrated")
    assert tmp_db.table_exists("schema_migrations")

    # Re-running should be idempotent
    tmp_db.run_migrations(mig_dir)


def test_context_manager(tmp_path):
    from src.utils.db import DatabaseManager
    db_path = tmp_path / "ctx.sqlite"
    with DatabaseManager(db_path) as db:
        db.execute("CREATE TABLE t (x TEXT)")
        db.execute("INSERT INTO t VALUES (?)", ("hello",))
    # Should have been committed and closed
    with DatabaseManager(db_path) as db:
        row = db.fetchone("SELECT x FROM t")
    assert row["x"] == "hello"
