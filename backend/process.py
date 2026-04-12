import pandas as pd
from sqlalchemy import create_engine
import os

DB_URL = os.getenv("DB_URL", "postgresql://admin:password123@db:5432/gnss_logs")
engine = create_engine(DB_URL)

def ingest_data(file_path):
    df = pd.read_csv(file_path)
    
    # BRONZE LAYER - Raw Backup (Data Engineers love this)
    df.to_sql('gnss_raw', engine, if_exists='append', index=False)

    # FILTERING LOGIC
    # Valid = Has coordinates AND Satellites > 4 AND SNR > 20
    is_valid = (df['lat'].notnull()) & (df['satellite_count'] > 4) & (df['snr'] > 20)
    
    valid_df = df[is_valid].copy()
    invalid_df = df[~is_valid].copy()
    
    # SILVER LAYER - Save Validated and Error data separately
    valid_df.to_sql('gnss_silver_valid', engine, if_exists='append', index=False)
    invalid_df.to_sql('gnss_silver_errors', engine, if_exists='append', index=False)
    
    return len(valid_df), len(invalid_df)