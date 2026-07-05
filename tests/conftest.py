import hashlib
import json
import os
from pathlib import Path

import psycopg
import pytest

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgres://kontent:kontent@localhost:5432/superpsychology_test"
)
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _apply_migrations(conn: psycopg.Connection) -> None:
    """Rebuild the schema from web's committed Drizzle SQL, then seed Drizzle's
    migration journal so web's migrate() sees the schema as up to date.

    Drizzle's migrator compares each migration's folderMillis (the "when" in
    meta/_journal.json) against the newest created_at in
    drizzle.__drizzle_migrations and re-applies anything newer; the hash it
    records is sha256 of the raw .sql file text. Seeding both keeps the two
    test suites (worker: raw SQL here; web: drizzle migrate()) interoperable
    on the shared test database.
    """
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cur.execute("DROP SCHEMA IF EXISTS drizzle CASCADE")
        cur.execute("CREATE SCHEMA public")
        cur.execute("CREATE SCHEMA drizzle")
        cur.execute(
            'CREATE TABLE drizzle."__drizzle_migrations" '
            "(id SERIAL PRIMARY KEY, hash text NOT NULL, created_at bigint)"
        )
    journal = json.loads((MIGRATIONS_DIR / "meta" / "_journal.json").read_text())
    for entry in journal["entries"]:
        sql_text = (MIGRATIONS_DIR / f"{entry['tag']}.sql").read_text()
        with conn.cursor() as cur:
            for stmt in sql_text.split("--> statement-breakpoint"):
                if stmt.strip():
                    cur.execute(stmt)
            cur.execute(
                'INSERT INTO drizzle."__drizzle_migrations" (hash, created_at) VALUES (%s, %s)',
                (hashlib.sha256(sql_text.encode()).hexdigest(), entry["when"]),
            )
    conn.commit()


@pytest.fixture(scope="session")
def test_db_url() -> str:
    with psycopg.connect(TEST_DB_URL) as conn:
        _apply_migrations(conn)
    return TEST_DB_URL


@pytest.fixture()
def conn(test_db_url):
    with psycopg.connect(test_db_url) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE TABLE posts, jobs, series, users RESTART IDENTITY CASCADE")
        c.commit()
        yield c
