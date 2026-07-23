-- =============================================================================
-- 003_timescale_policies.sql
-- Hypertable conversion, continuous aggregates, compression and retention
-- policies for the GNSS silver-valid time-series data.
--
-- TRANSACTION-SAFETY NOTE
-- ------------------------
-- The original backend/db.py wrapped create_hypertable() in a bare
-- try/except in Python. That's a latent bug: if that statement fails inside
-- an open Postgres transaction, the transaction is left in the "aborted"
-- state, and EVERY statement executed afterwards on that same connection/
-- transaction fails with `current transaction is aborted, commands ignored
-- until end of transaction block` — even though the Python except swallowed
-- the error and the script looked like it kept going.
--
-- Fixed two ways here:
--   1. create_hypertable() is called with if_not_exists => TRUE, which is
--      idempotent and does not raise on repeat runs.
--   2. Anything that legitimately might already exist (policies, the
--      continuous aggregate) is wrapped in a DO block with its own
--      EXCEPTION handler, which creates an implicit subtransaction/savepoint
--      in PL/pgSQL — so a failure there does NOT poison the outer
--      transaction the way a raw SQL error would. backend/db.py additionally
--      runs each migration file as its own transaction and rolls back +
--      logs (rather than silently continuing) on real failures.
-- =============================================================================

-- 1) Convert gnss_silver_valid into a hypertable, partitioned on time.
SELECT create_hypertable(
    'gnss_silver_valid',
    'time',
    if_not_exists => TRUE,
    migrate_data => TRUE
);


-- 2) Continuous aggregate: hourly rollup used by backend/report.py.
-- Continuous aggregates can't contain window functions, so this stays as
-- plain aggregates; a moving-average view is layered on top below.
DO $$
BEGIN
    CREATE MATERIALIZED VIEW IF NOT EXISTS gnss_hourly_agg
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time)               AS bucket,
        count(*)                                   AS reading_count,
        avg(alt)                                    AS avg_alt,
        avg(snr)                                    AS avg_snr,
        avg(satellite_count)                        AS avg_satellite_count,
        min(alt)                                    AS min_alt,
        max(alt)                                    AS max_alt
    FROM gnss_silver_valid
    GROUP BY bucket
    WITH NO DATA;
EXCEPTION WHEN duplicate_table OR duplicate_object THEN
    RAISE NOTICE 'gnss_hourly_agg already exists, skipping.';
END;
$$;

-- Continuous aggregate refresh policy: keep the last 3 days rolling,
-- refreshed every 30 minutes, ignoring the most recent 1 hour (still
-- filling in) so we don't refresh half-open buckets repeatedly.
DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy(
        'gnss_hourly_agg',
        start_offset      => INTERVAL '3 days',
        end_offset        => INTERVAL '1 hour',
        schedule_interval  => INTERVAL '30 minutes'
    );
EXCEPTION WHEN duplicate_object OR unique_violation THEN
    RAISE NOTICE 'Continuous aggregate policy already exists, skipping.';
END;
$$;


-- 3) BI-style daily rollup with a moving average, built as a regular view
-- on top of the continuous aggregate (window functions are not permitted
-- inside the continuous aggregate definition itself). This is the shape of
-- query a planning/reporting dashboard actually runs: a rollup plus
-- trend-over-time comparison.
CREATE OR REPLACE VIEW gnss_daily_quality_trend AS
WITH daily AS (
    SELECT
        time_bucket('1 day', bucket)                    AS day,
        sum(reading_count)                                AS total_readings,
        avg(avg_snr)                                      AS avg_snr,
        avg(avg_satellite_count)                          AS avg_satellite_count
    FROM gnss_hourly_agg
    GROUP BY day
)
SELECT
    day,
    total_readings,
    round(avg_snr::numeric, 2)              AS avg_snr,
    round(avg_satellite_count::numeric, 2)  AS avg_satellite_count,
    round(
        avg(avg_snr) OVER (
            ORDER BY day
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )::numeric, 2
    )                                        AS avg_snr_7d_moving_avg,
    round(
        (avg_snr - LAG(avg_snr) OVER (ORDER BY day))::numeric, 2
    )                                        AS avg_snr_change_vs_prev_day
FROM daily
ORDER BY day DESC;

COMMENT ON VIEW gnss_daily_quality_trend IS
    'BI-style daily rollup: signal-quality trend with a 7-day moving average '
    'and day-over-day delta, built on top of gnss_hourly_agg.';


-- 4) Compression policy: compress chunks older than 7 days. Segment by
-- nothing extra here since queries mostly filter by time; order by time
-- inside the chunk for good compression ratio on this workload.
ALTER TABLE gnss_silver_valid SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC'
);

DO $$
BEGIN
    PERFORM add_compression_policy('gnss_silver_valid', INTERVAL '7 days');
EXCEPTION WHEN duplicate_object OR unique_violation THEN
    RAISE NOTICE 'Compression policy already exists, skipping.';
END;
$$;


-- 5) Retention policy: raw high-frequency telemetry rarely needs to be kept
-- forever. Drop chunks older than 90 days from the valid hypertable. The
-- gnss_hourly_agg continuous aggregate survives independently, so long-term
-- rollup history is preserved even after raw rows age out.
DO $$
BEGIN
    PERFORM add_retention_policy('gnss_silver_valid', INTERVAL '90 days');
EXCEPTION WHEN duplicate_object OR unique_violation THEN
    RAISE NOTICE 'Retention policy already exists, skipping.';
END;
$$;
