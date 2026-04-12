def get_hourly_report():
    conn = get_connection()
    # Gets average altitude and count of pings per hour
    query = """
    SELECT time_bucket('1 hour', time) AS bucket,
           count(*),
           avg(alt)
    FROM valid_gnss_data
    GROUP BY bucket ORDER BY bucket DESC;
    """
    report = pd.read_sql(query, conn)
    conn.close()
    return report