# GNSS Reading Validation Rules

## Source of truth

As of Version 2, these rules are implemented **once**, in PL/pgSQL, as
`fn_classify_gnss_reading()` in
[`db/migrations/002_validation.sql`](../db/migrations/002_validation.sql),
and applied automatically to every row inserted into `gnss_raw` via the
`trg_classify_gnss_on_insert` trigger.

This document describes the rules; it does not define them. If this doc and
the SQL ever disagree, the SQL wins — read the function directly.

In Version 1, these rules existed only as a pandas boolean mask inside
`backend/process.py`. That worked for the one ingestion path that went
through `ingest_data()`, but any other writer into the raw table (a bulk
loader, a future streaming consumer, a manual `COPY`) would have bypassed
validation entirely. Moving the rules into a trigger means classification
happens in the database itself, regardless of how a row got there.

## Rules

Checked in order; the first rule a row fails is the recorded
`rejection_reason`. A row that passes all three is written to
`gnss_silver_valid`.

| # | Rule | Condition to reject | Rejection reason |
|---|------|----------------------|-------------------|
| 1 | Coordinate integrity | `lat IS NULL OR lon IS NULL` | `missing_coordinates` |
| 2 | Satellite count | `satellite_count IS NULL OR satellite_count <= 4` | `insufficient_satellites` |
| 3 | Signal strength (SNR) | `snr IS NULL OR snr <= 20` | `low_snr` |

## Behavior change from Version 1

The original Python logic only checked `df['lat'].notnull()` for coordinate
integrity — a row with a valid `lat` but a `NULL` `lon` would have
incorrectly passed validation. The PL/pgSQL version checks both `lat` and
`lon`. If you're comparing row counts against an older run of this project,
this is why the valid/error split may shift slightly.

## Where classification happens

```
gnss_raw (bronze, INSERT)
      │
      ▼  AFTER INSERT trigger: trg_classify_gnss_on_insert
      │
      ├─▶ fn_classify_gnss_reading() returns NULL  ─▶ gnss_silver_valid
      │
      └─▶ fn_classify_gnss_reading() returns reason ─▶ gnss_silver_errors
```

`backend/process.py` now only inserts into `gnss_raw`. It queries
`gnss_silver_valid` / `gnss_silver_errors` back (filtered by
`source_raw_id`) purely to report a valid/error count to the caller — it
does not perform or duplicate the classification itself.
