# Changelog

## Version 2 — DB-side validation, TimescaleDB policies, query optimization

### Added
- `db/migrations/001_schema.sql` — bronze/silver table DDL, extracted out of `backend/db.py`.
- `db/migrations/002_validation.sql` — `fn_classify_gnss_reading()` PL/pgSQL function and `trg_classify_gnss_on_insert` trigger; classification is now DB-side and applies to every writer into `gnss_raw`.
- `db/migrations/003_timescale_policies.sql` — hypertable conversion, `gnss_hourly_agg` continuous aggregate, `gnss_daily_quality_trend` BI rollup view (7-day moving average, day-over-day delta), compression policy (7 days), retention policy (90 days).
- `backend/config.py` — single source for `DB_URL` and the migrations path, replacing per-file `os.getenv()` duplication.
- `scripts/query_optimization.py` — seeds 500k rows, captures real `EXPLAIN (ANALYZE, BUFFERS)` before/after a composite index, writes results to `docs/query_optimization_results.md`.
- `docs/validation_rules.md` — documents the PL/pgSQL rules as the single source of truth.
- `docs/query_optimization_results.md` — placeholder until run against a live Postgres instance.

### Changed
- `backend/db.py` — now a migration runner (applies `db/migrations/*.sql` in filename order), each file in its own transaction with explicit rollback on failure.
- `backend/process.py` — inserts only into `gnss_raw` (bronze); classification is delegated to the DB trigger instead of a pandas boolean mask.
- `backend/report.py` — fixed (previously referenced an undefined `get_connection` and a non-existent table); now reads from `gnss_hourly_agg` and `gnss_daily_quality_trend` instead of scanning raw rows.
- `dashboard/app.py` — imports `DB_URL` from `backend.config`; added a "Rollup Trends" section using the new report functions.
- `README.md` — added Project Structure, Database-Side Additions, and Version 1 vs. Version 2 sections.

### Fixed
- Coordinate-integrity check now rejects rows with a `NULL` `lon` (previously only `lat` was checked).
- Transaction-poisoning bug: a failed `create_hypertable()` call (or any DDL) no longer silently aborts the connection for every subsequent statement.
