import pandas as pd
from sqlalchemy import create_engine, text

from backend.config import DB_URL

engine = create_engine(DB_URL)


def ingest_data(file_path):
    """
    Version 2 ingestion.

    V1 (original): pandas computed the valid/invalid boolean mask in Python
    and wrote to gnss_silver_valid / gnss_silver_errors directly. That logic
    only applied to rows that went through this exact function -- any other
    writer into gnss_raw would bypass validation entirely.

    V2 (this version): Python's only job is to land rows in the gnss_raw
    bronze table. Classification is delegated to the
    trg_classify_gnss_on_insert trigger (db/migrations/002_validation.sql),
    which is PL/pgSQL and fires on every insert into gnss_raw regardless of
    who or what is writing to it. That makes the database the single source
    of truth for what counts as a valid GNSS reading.
    """
    df = pd.read_csv(file_path)

    with engine.begin() as conn:
        before_max_id = conn.execute(
            text("SELECT COALESCE(max(id), 0) FROM gnss_raw")
        ).scalar()

        df.to_sql("gnss_raw", conn, if_exists="append", index=False)

        valid_count = conn.execute(
            text(
                "SELECT count(*) FROM gnss_silver_valid "
                "WHERE source_raw_id > :before_id"
            ),
            {"before_id": before_max_id},
        ).scalar()

        error_count = conn.execute(
            text(
                "SELECT count(*) FROM gnss_silver_errors "
                "WHERE source_raw_id > :before_id"
            ),
            {"before_id": before_max_id},
        ).scalar()

    return valid_count, error_count
