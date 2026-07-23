import os
import time
import glob

import psycopg2

from backend.config import DB_URL, MIGRATIONS_DIR


def _connect_with_retry(retries=5, delay=2):
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(DB_URL)
        except psycopg2.OperationalError as e:
            print(f"Retrying connection ({attempt}/{retries})... ({e})")
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to DB after {retries} attempts.")


def _run_migration_file(conn, path):
    """
    Execute a single .sql migration file as its own transaction.

    Bug this replaces: the previous version ran create_hypertable() inside a
    bare try/except in Python. If that statement failed, the underlying
    Postgres transaction was left ABORTED, but the except block swallowed
    the error and returned as if nothing happened -- so every statement run
    afterwards on that connection would silently fail with
    "current transaction is aborted, commands ignored until end of
    transaction block", and the caller had no idea why.

    Fix: each migration file gets its own transaction. On failure we roll
    back explicitly (returning the connection to a clean, usable state) and
    re-raise, so the caller sees a real error instead of a poisoned
    connection.
    """
    with open(path, "r") as f:
        sql = f.read()

    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        print(f"  [ok] applied {os.path.basename(path)}")
    except Exception as e:
        conn.rollback()
        print(f"  [fail] {os.path.basename(path)}: {e}")
        raise
    finally:
        cur.close()


def init_db():
    print("Connecting to database to initialize...")
    conn = _connect_with_retry()

    try:
        migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

        if not migration_files:
            print(f"WARNING: No migration files found in {MIGRATIONS_DIR}")
            return

        print(f"Applying {len(migration_files)} migration(s) from {MIGRATIONS_DIR}:")
        for path in migration_files:
            _run_migration_file(conn, path)

        print("Database initialization complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
