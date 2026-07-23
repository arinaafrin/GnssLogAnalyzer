import pandas as pd
import psycopg2

from backend.config import DB_URL


def get_connection():
    return psycopg2.connect(DB_URL)


def get_hourly_report():
    """
    V1 (original, and broken as written): scanned gnss_silver_valid raw rows
    with a time_bucket() GROUP BY on every call -- get_connection() and the
    pandas import weren't even defined in this file, and it queried a table
    (valid_gnss_data) that doesn't exist in this schema. Also, grouping raw
    rows on every dashboard refresh means the aggregation cost scales with
    total row count forever.

    V2: reads from gnss_hourly_agg, the TimescaleDB continuous aggregate
    defined in db/migrations/003_timescale_policies.sql. The rollup is
    maintained incrementally by Timescale's background refresh policy, so
    this query is fast regardless of how much raw history has accumulated.
    """
    conn = get_connection()
    try:
        query = """
            SELECT
                bucket,
                reading_count,
                avg_alt,
                avg_snr,
                avg_satellite_count
            FROM gnss_hourly_agg
            ORDER BY bucket DESC;
        """
        report = pd.read_sql(query, conn)
    finally:
        conn.close()
    return report


def get_daily_quality_trend():
    """
    BI-style rollup: daily signal quality with a 7-day moving average and
    day-over-day delta. Backed by the gnss_daily_quality_trend view, which
    layers window functions on top of gnss_hourly_agg (continuous
    aggregates themselves can't contain window functions).
    """
    conn = get_connection()
    try:
        report = pd.read_sql("SELECT * FROM gnss_daily_quality_trend;", conn)
    finally:
        conn.close()
    return report
