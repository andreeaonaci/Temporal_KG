-- ─────────────────────────────────────────────────────────────────────────────
-- 001_core_schema.sql
-- Initial schema for the temporal knowledge graph project.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Sources ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    url         TEXT    NOT NULL UNIQUE,
    country     TEXT,
    feed_type   TEXT    DEFAULT 'rss',   -- rss | scrape | api
    credibility REAL    DEFAULT 0.5,
    created_at  TEXT    DEFAULT (datetime('now')),
    updated_at  TEXT    DEFAULT (datetime('now'))
);

-- ── Articles ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    url             TEXT    NOT NULL UNIQUE,
    title           TEXT,
    content_raw     TEXT,
    content_clean   TEXT,
    language        TEXT    DEFAULT 'en',
    country         TEXT,
    published_at    TEXT,                -- ISO-8601
    fetched_at      TEXT    DEFAULT (datetime('now')),
    status          TEXT    DEFAULT 'raw',  -- raw | cleaned | extracted | exported
    content_hash    TEXT,
    credibility     REAL
);

CREATE INDEX IF NOT EXISTS idx_articles_status       ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_country      ON articles(country);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);

-- ── Entities ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    type        TEXT    NOT NULL,   -- PERSON | ORG | GPE | LOC | EVENT | NORP
    canonical   TEXT,               -- normalised form
    description TEXT,
    created_at  TEXT    DEFAULT (datetime('now')),
    UNIQUE(name, type)
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

-- ── Article ↔ Entity mentions ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS article_entities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id    INTEGER NOT NULL REFERENCES articles(id)  ON DELETE CASCADE,
    entity_id     INTEGER NOT NULL REFERENCES entities(id)  ON DELETE CASCADE,
    mention_text  TEXT,
    mention_count INTEGER DEFAULT 1,
    confidence    REAL    DEFAULT 1.0,
    UNIQUE(article_id, entity_id)
);

-- ── Relations ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS relations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id    INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    subject_id    INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    predicate     TEXT    NOT NULL,
    object_id     INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    confidence    REAL    DEFAULT 1.0,
    temporal_ref  TEXT,             -- ISO-8601 date/interval this relation holds
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_relations_subject   ON relations(subject_id);
CREATE INDEX IF NOT EXISTS idx_relations_object    ON relations(object_id);
CREATE INDEX IF NOT EXISTS idx_relations_predicate ON relations(predicate);

-- ── Temporal expressions ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS temporal_expressions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id    INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    raw_text      TEXT    NOT NULL,
    normalized    TEXT,             -- ISO-8601 or interval
    granularity   TEXT,             -- year | month | day | hour
    confidence    REAL    DEFAULT 1.0,
    created_at    TEXT    DEFAULT (datetime('now'))
);

-- ── Ingestion run log ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER REFERENCES sources(id),
    started_at    TEXT    DEFAULT (datetime('now')),
    finished_at   TEXT,
    articles_new  INTEGER DEFAULT 0,
    articles_dup  INTEGER DEFAULT 0,
    errors        INTEGER DEFAULT 0,
    status        TEXT    DEFAULT 'running'  -- running | success | failed
);
