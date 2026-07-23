-- =============================================================================
-- 002_validation.sql
-- DB-side data-quality validation for GNSS readings, in PL/pgSQL.
--
-- WHY THIS EXISTS
-- ----------------
-- Version 1 of this project computed validity in pandas inside
-- backend/process.py (a boolean mask), then wrote the valid/invalid rows to
-- two separate tables from Python. That means the *rules* only exist in one
-- ingestion path. Any second writer (a bulk loader, a future streaming
-- consumer, someone doing a manual COPY) bypasses validation entirely and
-- silently pollutes the "clean" table.
--
-- Version 2 moves classification into the database itself, as a trigger on
-- gnss_raw. Every row that lands in gnss_raw — no matter how it got there —
-- is classified by the SAME function and routed to gnss_silver_valid or
-- gnss_silver_errors. The DB is the single source of truth; docs/validation_rules.md
-- documents these rules as PL/pgSQL, not as a Python code excerpt.
--
-- RULES (kept identical to the original pandas logic, bug-fixed where the
-- original was ambiguous — see inline notes):
--   1. Coordinates must be present            -> reason: 'missing_coordinates'
--   2. satellite_count must be > 4             -> reason: 'insufficient_satellites'
--   3. snr must be > 20                        -> reason: 'low_snr'
--   Checked in that order; the first rule that fails is the recorded reason.
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_classify_gnss_reading(
    p_lat  DOUBLE PRECISION,
    p_lon  DOUBLE PRECISION,
    p_sat  INT,
    p_snr  DOUBLE PRECISION
) RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    -- Rule 1: coordinate integrity.
    -- Original Python only checked df['lat'].notnull(); a row with a valid
    -- lat but a NULL lon would have passed. Fixed here: both must be present.
    IF p_lat IS NULL OR p_lon IS NULL THEN
        RETURN 'missing_coordinates';
    END IF;

    -- Rule 2: satellite count filtering.
    IF p_sat IS NULL OR p_sat <= 4 THEN
        RETURN 'insufficient_satellites';
    END IF;

    -- Rule 3: SNR (signal strength) validation.
    IF p_snr IS NULL OR p_snr <= 20 THEN
        RETURN 'low_snr';
    END IF;

    -- NULL means "valid" — no rejection reason.
    RETURN NULL;
END;
$$;

COMMENT ON FUNCTION fn_classify_gnss_reading IS
    'Single source of truth for GNSS row validity. Returns a rejection reason, '
    'or NULL if the row is valid. Mirrors docs/validation_rules.md.';


-- Trigger function: on every row inserted into gnss_raw, classify it and
-- route a copy into gnss_silver_valid or gnss_silver_errors.
CREATE OR REPLACE FUNCTION trg_fn_classify_and_route_gnss()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_reason TEXT;
BEGIN
    v_reason := fn_classify_gnss_reading(NEW.lat, NEW.lon, NEW.satellite_count, NEW.snr);

    IF v_reason IS NULL THEN
        INSERT INTO gnss_silver_valid (time, lat, lon, alt, satellite_count, snr, source_raw_id)
        VALUES (NEW.time, NEW.lat, NEW.lon, NEW.alt, NEW.satellite_count, NEW.snr, NEW.id);
    ELSE
        INSERT INTO gnss_silver_errors (time, lat, lon, alt, satellite_count, snr, rejection_reason, source_raw_id)
        VALUES (NEW.time, NEW.lat, NEW.lon, NEW.alt, NEW.satellite_count, NEW.snr, v_reason, NEW.id);
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_classify_gnss_on_insert ON gnss_raw;

CREATE TRIGGER trg_classify_gnss_on_insert
    AFTER INSERT ON gnss_raw
    FOR EACH ROW
    EXECUTE FUNCTION trg_fn_classify_and_route_gnss();

COMMENT ON TRIGGER trg_classify_gnss_on_insert ON gnss_raw IS
    'Routes every inserted row to gnss_silver_valid/gnss_silver_errors using '
    'fn_classify_gnss_reading, so classification cannot be bypassed by any writer.';
