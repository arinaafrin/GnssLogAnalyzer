import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, inspect
import os
import sys

# Backend imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.process import ingest_data
from backend.db import init_db
from backend.report import get_hourly_report, get_daily_quality_trend
from backend.config import DB_URL

# DB CONFIG
engine = create_engine(DB_URL)

st.set_page_config(page_title="GNSS Log Analyzer Pro", layout="wide")

# SESSION STATE
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

# HELPERS
def get_db_status():
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        required = ["gnss_raw", "gnss_silver_valid", "gnss_silver_errors"]
        return all(t in tables for t in required)
    except:
        return False


def compute_health_score(raw, valid):
    return round((valid / (raw + 1e-9)) * 100, 2)


def detect_outliers(df, col):
    if col not in df.columns:
        return pd.DataFrame()

    q1 = df[col].quantile(0.25)
    q3 = df[col].quantile(0.75)
    iqr = q3 - q1
    return df[(df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)]


# HEADER
st.title("🛰️ GNSS Log & Quality Analyzer Pro")
st.markdown("---")

# SIDEBAR
st.sidebar.header("🕹️ Control Panel")
view_mode = st.sidebar.selectbox(
    "Switch View",
    ["Operational Dashboard", "Report"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📤 Upload GNSS Logs")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type="csv")

# BOOTSTRAP DB
if not get_db_status():
    st.warning("⚠️ Database not initialized.")
    if st.button("🛠️ Initialize DB + Load Sample Data"):
        with st.spinner("Bootstrapping pipeline..."):
            try:
                init_db()
                sample_path = "data/sample_gnss.csv"
                if os.path.exists(sample_path):
                    v, e = ingest_data(sample_path)
                    st.success(f"Loaded {v} valid rows, {e} errors")
                    st.rerun()
                else:
                    st.error("Sample file missing.")
            except Exception as e:
                st.error(str(e))
    st.stop()

# FILE INGESTION
if uploaded_file is not None:
    if uploaded_file.name not in st.session_state.processed_files:

        temp_path = os.path.join("data", "temp_upload.csv")
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner("Processing file..."):
            try:
                valid_count, error_count = ingest_data(temp_path)

                st.session_state.processed_files.add(uploaded_file.name)

                st.sidebar.success(f"Ingested {valid_count} rows")
                if error_count > 0:
                    st.sidebar.warning(f"{error_count} errors filtered")

                st.rerun()

            except Exception as e:
                st.sidebar.error(f"Upload failed: {e}")
    else:
        st.sidebar.info("File already processed")

# SHARED METRICS (GLOBAL SCOPE)
raw_count = int(pd.read_sql("SELECT count(*) FROM gnss_raw", engine).iloc[0, 0])
valid_count = int(pd.read_sql("SELECT count(*) FROM gnss_silver_valid", engine).iloc[0, 0])

err_df = pd.read_sql("SELECT * FROM gnss_silver_errors LIMIT 1000", engine)
error_count = len(err_df)

health = compute_health_score(raw_count, valid_count)

# OPERATIONAL DASHBOARD
if view_mode == "Operational Dashboard":

    st.subheader("📍 Live GNSS Telemetry")

    df_valid = pd.read_sql(
        "SELECT * FROM gnss_silver_valid ORDER BY time DESC LIMIT 2000",
        engine
    )

    if df_valid.empty:
        st.info("No data available")
        st.stop()

    col1, col2, col3 = st.columns(3)

    col1.metric("Avg Satellites", round(df_valid["satellite_count"].mean(), 1))
    col2.metric("Avg SNR", round(df_valid["snr"].mean(), 1))
    col3.metric("Records", len(df_valid))

    df_valid["time"] = pd.to_datetime(df_valid["time"])

    st.subheader("🗺️ GNSS Path")
    st.map(df_valid[["lat", "lon"]].dropna().rename(
        columns={"lat": "latitude", "lon": "longitude"}
    ))

    st.subheader("📈 Altitude Trend")
    st.line_chart(df_valid.set_index("time")["alt"])

    st.subheader("📡 Signal Trends")
    st.line_chart(df_valid.set_index("time")[["snr", "satellite_count"]])


# DATA ENGINEERING REPORT
else:

    st.subheader("📊 Pipeline Health Overview")

    raw_count = int(pd.read_sql("SELECT count(*) FROM gnss_raw", engine).iloc[0, 0])
    valid_count = int(pd.read_sql("SELECT count(*) FROM gnss_silver_valid", engine).iloc[0, 0])
    err_df = pd.read_sql("SELECT * FROM gnss_silver_errors LIMIT 1000", engine)

    error_count = len(err_df)
    health = compute_health_score(raw_count, valid_count)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Raw Rows", raw_count)
    c2.metric("Valid Rows", valid_count)
    c3.metric("Errors", error_count)
    c4.metric("Health %", health)

    # DATA DISTRIBUTION
    st.subheader("📉 Data Distribution")

    df_valid = pd.read_sql(
        "SELECT * FROM gnss_silver_valid ORDER BY time DESC LIMIT 5000",
        engine
    )

    if not df_valid.empty:
        metric = st.selectbox("Select Metric", ["snr", "satellite_count", "alt"])

        if metric in df_valid.columns:
            st.bar_chart(df_valid[metric].value_counts().sort_index())

            outliers = detect_outliers(df_valid, metric)
            st.metric("Outliers detected", len(outliers))

    # ERROR INTELLIGENCE
    st.subheader("🚨 Error Intelligence")

    if not err_df.empty:
        st.bar_chart(err_df["rejection_reason"].value_counts())

        st.dataframe(err_df[[
            "time", "rejection_reason", "snr", "satellite_count"
        ]].head(20))
    else:
        st.success("No errors detected")

    # DATA FRESHNESS
    st.subheader("⏱️ Data Freshness")

    if not df_valid.empty:
        df_valid["time"] = pd.to_datetime(df_valid["time"], utc=True)

        last_time = df_valid["time"].max()

        st.metric("Last Update", str(last_time))

        now = pd.Timestamp.now(tz="UTC")

        age_sec = (now - last_time).total_seconds()

        st.metric("Data Age (sec)", int(age_sec))

        # RAW AUDIT TRAIL
        st.subheader("🧾 Raw Data Audit Trail")

        st.dataframe(pd.read_sql(
            "SELECT * FROM gnss_raw LIMIT 20",
            engine
        ))

    # ROLLUP TRENDS (TimescaleDB continuous aggregate + BI-style daily view)
    st.subheader("📈 Rollup Trends (Continuous Aggregate)")

    try:
        hourly_df = get_hourly_report()
        if not hourly_df.empty:
            hourly_df["bucket"] = pd.to_datetime(hourly_df["bucket"])
            st.caption("Hourly rollup from gnss_hourly_agg (continuous aggregate)")
            st.line_chart(hourly_df.set_index("bucket")[["avg_snr", "avg_satellite_count"]])
        else:
            st.info("No rollup data yet — the continuous aggregate refreshes on a schedule.")

        daily_df = get_daily_quality_trend()
        if not daily_df.empty:
            daily_df["day"] = pd.to_datetime(daily_df["day"])
            st.caption("Daily signal quality with 7-day moving average (gnss_daily_quality_trend)")
            st.line_chart(daily_df.set_index("day")[["avg_snr", "avg_snr_7d_moving_avg"]])
            st.dataframe(daily_df.head(14))
    except Exception as e:
        st.warning(f"Rollup views not available yet: {e}")

    # EXECUTIVE SUMMARY
    st.subheader("📋 Executive Summary")

    df_valid = pd.read_sql(
        "SELECT * FROM gnss_silver_valid ORDER BY time DESC LIMIT 5000",
        engine
    )

    summary = {
        "Pipeline Health %": health,
        "Error Rate %": round((error_count / (raw_count + 1e-9)) * 100, 2),
        "Avg SNR": round(df_valid["snr"].mean(), 2) if not df_valid.empty else 0,
        "Avg Satellites": round(df_valid["satellite_count"].mean(), 2) if not df_valid.empty else 0,
    }

    st.json(summary)

