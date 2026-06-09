-- ─────────────────────────────────────────────────────────────────────────────
-- 002_ingestion_layer.sql
-- Extends the core schema with ingestion-layer columns and feed registry.
-- ─────────────────────────────────────────────────────────────────────────────

-- Add ingestion columns to articles if not present
-- (SQLite does not support IF NOT EXISTS on ALTER TABLE columns pre-3.37,
--  so we use separate statements wrapped in the migration runner.)

ALTER TABLE articles ADD COLUMN content_hash_url  TEXT;  -- SHA-256 of URL (dedup key)
ALTER TABLE articles ADD COLUMN is_relevant        INTEGER DEFAULT 0;  -- 1=relevant
ALTER TABLE articles ADD COLUMN relevance_reason   TEXT;
ALTER TABLE articles ADD COLUMN raw_html_path      TEXT;  -- relative path to saved HTML
ALTER TABLE articles ADD COLUMN json_path          TEXT;  -- relative path to saved JSON
ALTER TABLE articles ADD COLUMN language_detected  TEXT;
ALTER TABLE articles ADD COLUMN fetch_error        TEXT;  -- last error message if any

-- Feed registry (richer than sources table — tracks per-feed state)
CREATE TABLE IF NOT EXISTS feeds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    url             TEXT    NOT NULL UNIQUE,
    country         TEXT,
    credibility     REAL    DEFAULT 0.5,
    last_fetched_at TEXT,
    last_etag       TEXT,
    last_modified   TEXT,
    articles_total  INTEGER DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feeds_country ON feeds(country);

-- Extend ingestion_runs to link to feeds
ALTER TABLE ingestion_runs ADD COLUMN feed_id       INTEGER REFERENCES feeds(id);
ALTER TABLE ingestion_runs ADD COLUMN feed_url      TEXT;
ALTER TABLE ingestion_runs ADD COLUMN articles_relevant INTEGER DEFAULT 0;
