-- =============================================================================
-- 001_schema.sql
-- Base Bronze/Silver tables for the GNSS Log Analyzer.
--
-- This used to live as inline cur.execute() calls inside backend/db.py.
-- Moved into a versioned migration file so schema changes are reviewable,
-- diffable, and reusable outside of the Python app (psql, CI, migration
-- tooling, etc).
-- =============================================================================

-- BRONZE LAYER: raw, untouched ingestion. Nothing is ever rejected here —
-- it's the audit trail of "what did we actually receive".
CREATE TABLE IF NOT EXISTS gnss_raw (
    id               BIGSERIAL PRIMARY KEY,
    time             TIMESTAMPTZ NOT NULL,
    lat              DOUBLE PRECISION,
    lon              DOUBLE PRECISION,
    alt              DOUBLE PRECISION,
    satellite_count  INT,
    snr              DOUBLE PRECISION,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gnss_raw_time ON gnss_raw (time DESC);

-- SILVER LAYER (valid): rows that passed data-quality validation.
CREATE TABLE IF NOT EXISTS gnss_silver_valid (
    time             TIMESTAMPTZ NOT NULL,
    lat              DOUBLE PRECISION,
    lon              DOUBLE PRECISION,
    alt              DOUBLE PRECISION,
    satellite_count  INT,
    snr              DOUBLE PRECISION,
    source_raw_id    BIGINT
);

-- SILVER LAYER (errors): rows that failed validation, with the reason,
-- so every dropped record stays traceable.
CREATE TABLE IF NOT EXISTS gnss_silver_errors (
    time              TIMESTAMPTZ,
    lat               DOUBLE PRECISION,
    lon               DOUBLE PRECISION,
    alt               DOUBLE PRECISION,
    satellite_count   INT,
    snr               DOUBLE PRECISION,
    rejection_reason  TEXT NOT NULL,
    source_raw_id     BIGINT
);

CREATE INDEX IF NOT EXISTS idx_gnss_silver_errors_reason
    ON gnss_silver_errors (rejection_reason);
