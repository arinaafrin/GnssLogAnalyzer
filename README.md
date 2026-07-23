# 🛰️ GNSS Log Analyzer

A small data pipeline that takes raw GNSS (satellite) logs, validates them, stores them in a time-series database, and shows them on a live dashboard.

Built with a **Bronze → Silver** flow: raw data comes in untouched (Bronze), gets checked for quality, and only the good stuff moves on (Silver). Anything rejected is kept too, along with *why* it was rejected — nothing just disappears.

---

## What's in the stack

- **Python** (Pandas, SQLAlchemy) — ingestion
- **PostgreSQL + TimescaleDB** — storage, validation, rollups
- **Streamlit** — dashboard
- **Docker Compose** — runs the whole thing with one command

---

## How data flows

1. A CSV of GNSS readings comes in.
2. Python writes it straight into `gnss_raw` (no filtering yet).
3. A PostgreSQL trigger checks each row automatically and sorts it into:
   - `gnss_silver_valid` — good data
   - `gnss_silver_errors` — bad data, with a reason (missing coordinates, too few satellites, weak signal)
4. TimescaleDB keeps hourly/daily rollups up to date on its own, so the dashboard doesn't have to scan raw rows every time.
5. Old data gets compressed after 7 days and cleaned up after 90 — the rollups stick around either way.

The validation rules live in one place: `db/migrations/002_validation.sql`. That's the source of truth, not the Python code — so it's impossible to sneak data past the rules no matter how it gets inserted.

---

## Project layout

```
backend/       Python app code (config, DB init, ingestion, reporting)
dashboard/     Streamlit UI
db/migrations/ Versioned SQL — schema, validation trigger, TimescaleDB setup
scripts/       Query-optimization benchmark
docs/          Validation rules + benchmark results
data/          Sample CSV + generator
```

---

## Running it end-to-end

### 1. Start everything
```bash
docker-compose up --build -d
docker-compose ps
```
Both `db` and `app` should say `Up`. If `db` won't start, something on your machine is already using port 5432 — check with `netstat -ano | findstr :5432` (Windows) and either free it up or just change the host port in `docker-compose.yml` (e.g. `"5433:5432"`). You don't need to touch anything else — the app talks to `db` over Docker's internal network either way.

### 2. Set up the database
```bash
docker-compose exec app python -m backend.db
```
This runs the SQL migrations in order — creates the tables, sets up the validation trigger, and configures TimescaleDB. You'll see one line per migration confirming it applied.

### 3. Open the dashboard
Go to **http://localhost:8501** and click **"Initialize DB + Load Sample Data"** if it's your first run — this loads the sample CSV so you've got something to look at right away.

### 4. Try it out
- Upload your own CSV from the sidebar
- Switch to the **Report** view to see pipeline health, error breakdowns, and the rollup trend charts
- Check `gnss_silver_errors` in the DB if you want to see rejected rows and why

### 5. (Optional) Run the query-optimization benchmark
```bash
docker-compose exec app python -m scripts.query_optimization
```
Seeds 500k rows, runs a real `EXPLAIN ANALYZE` before and after adding an index, and writes the results to `docs/query_optimization_results.md`.

### 6. Shut down
```bash
docker-compose down       # keep your data
docker-compose down -v    # wipe it and start clean next time
```

---

## Changelog

**v2 — validation and rollups moved into the database**
- Validation logic moved from a Python script into a PostgreSQL trigger, so it applies no matter how data gets inserted (was a bug before: a missing longitude could sneak through)
- Added TimescaleDB rollups (hourly + daily with a moving average) so the dashboard doesn't scan raw data every time
- Added compression (after 7 days) and retention (after 90 days) so the database doesn't grow forever
- Fixed a bug where a failed setup step could silently break every query after it
- Fixed a broken reporting file that referenced things that didn't exist
- Added a script that benchmarks a real query before/after adding an index

**v1 — initial version**
- Basic Bronze/Silver pipeline with validation done in Python
- Streamlit dashboard for uploading and viewing data
- TimescaleDB used for storage, but without rollups, compression, or retention