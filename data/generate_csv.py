import pandas as pd
import numpy as np
from datetime import datetime, timedelta

rows = 10000
start_time = datetime.now()

data = {
    'time': [start_time + timedelta(seconds=i) for i in range(rows)],
    'lat': np.random.uniform(23.0, 24.0, rows),
    'lon': np.random.uniform(89.0, 90.0, rows),
    'alt': np.random.uniform(10, 50, rows),
    'satellite_count': np.random.randint(0, 12, rows), # Includes 0 for "bad" data
    'snr': np.random.uniform(5, 45, rows)             # Low SNR for filtering
}

df = pd.DataFrame(data)

# Inject "Missing Data" for the Data Engineers to find
df.iloc[100:150, 1:3] = np.nan 
df.to_csv('data/sample_gnss.csv', index=False)
print("Created 10,000 rows in data/sample_gnss.csv")