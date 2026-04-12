import psycopg2
import os
import time

# Get credentials from environment variables
DB_URL = os.getenv("DB_URL", "postgresql://admin:password123@db:5432/gnss_logs")

def init_db():
    print("⏳ Connecting to database to initialize...")
    # Retry logic because the DB container might take a few seconds to boot
    for i in range(5):
        try:
            conn = psycopg2.connect(DB_URL)
            break
        except:
            print(f"Retrying connection ({i+1}/5)...")
            time.sleep(2)
    else:
        print("❌ Could not connect to DB.")
        return

    cur = conn.cursor()

    # 1. 'Bronze' Table (Raw Backup)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gnss_raw (
            time TIMESTAMPTZ,
            lat DOUBLE PRECISION, lon DOUBLE PRECISION, alt DOUBLE PRECISION,
            satellite_count INT, snr DOUBLE PRECISION
        );
    """)

    # 2. 'Silver' Table (Validated Data)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gnss_silver_valid (
            time TIMESTAMPTZ NOT NULL,
            lat DOUBLE PRECISION, lon DOUBLE PRECISION, alt DOUBLE PRECISION,
            satellite_count INT, snr DOUBLE PRECISION
        );
    """)

    # 3. 'Silver' Table (Errors) - UPDATED TO INCLUDE LAT/LON/SNR
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gnss_silver_errors (
            time TIMESTAMPTZ,
            lat DOUBLE PRECISION, lon DOUBLE PRECISION, alt DOUBLE PRECISION,
            satellite_count INT, snr DOUBLE PRECISION,
            rejection_reason TEXT
        );
    """)

    # 4. Turn the Valid table into a TimescaleDB Hypertable
    try:
        cur.execute("SELECT create_hypertable('gnss_silver_valid', 'time', if_not_exists => TRUE);")
        print("🚀 Hypertable created successfully!")
    except Exception as e:
        print(f"Note: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialization complete.")

if __name__ == "__main__":
    init_db()