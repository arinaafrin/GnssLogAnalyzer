import os

DB_URL = os.getenv("DB_URL", "postgresql://admin:password123@db:5432/gnss_logs")
if DB_URL.startswith("postgres://"):
    DB_URL = "postgresql://" + DB_URL[len("postgres://"):]

# Migrations are applied in filename order by backend.db.init_db().
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "migrations"
)
