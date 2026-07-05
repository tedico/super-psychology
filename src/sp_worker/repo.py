"""Job/series data access. Schema is owned by web's Drizzle migrations."""

import json
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json


def connect(database_url: str) -> psycopg.Connection:
    # Plain tuple rows at the connection level; _one() opts into dict_row
    # per-cursor. (Connection-level dict_row would break the tuple-indexing
    # cursors in create_job/used_topics.)
    return psycopg.connect(database_url)


def _one(conn: psycopg.Connection, query: str, params: tuple) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"no row for {query.split()[3]} {params}")
        return row


def fetch_job(conn, job_id) -> dict[str, Any]:
    return _one(conn, "SELECT * FROM jobs WHERE id = %s", (job_id,))


def fetch_series(conn, series_id) -> dict[str, Any]:
    return _one(conn, "SELECT * FROM series WHERE id = %s", (series_id,))


def create_job(conn, series_id) -> str:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO jobs (series_id) VALUES (%s) RETURNING id", (series_id,))
        job_id = cur.fetchone()[0]
    conn.commit()
    return job_id


def start_job(conn, job_id) -> None:
    _exec(conn, "UPDATE jobs SET status = 'running', updated_at = now() WHERE id = %s", (job_id,))


def set_stage(conn, job_id, stage: str, status: str, seconds: float | None = None) -> None:
    entry: dict[str, Any] = {"status": status}
    if seconds is not None:
        entry["seconds"] = round(seconds, 3)
    _exec(
        conn,
        "UPDATE jobs SET stage_status = stage_status || %s::jsonb, updated_at = now() WHERE id = %s",
        (json.dumps({stage: entry}), job_id),
    )


def add_cost(conn, job_id, usd: float) -> None:
    _exec(
        conn,
        "UPDATE jobs SET cost_usd = cost_usd + %s, updated_at = now() WHERE id = %s",
        (usd, job_id),
    )


def save_script(conn, job_id, *, topic, script, title, description, hashtags) -> None:
    _exec(
        conn,
        """UPDATE jobs SET topic = %s, script = %s, title = %s, description = %s,
           hashtags = %s, updated_at = now() WHERE id = %s""",
        (topic, script, title, description, Json(hashtags), job_id),
    )


def set_asset(conn, job_id, key: str, path: str) -> None:
    _exec(
        conn,
        "UPDATE jobs SET asset_paths = asset_paths || %s::jsonb, updated_at = now() WHERE id = %s",
        (json.dumps({key: path}), job_id),
    )


def finish_job(conn, job_id) -> None:
    _exec(conn, "UPDATE jobs SET status = 'done', updated_at = now() WHERE id = %s", (job_id,))


def fail_job(conn, job_id, *, stage: str, message: str) -> None:
    _exec(
        conn,
        "UPDATE jobs SET status = 'failed', error = %s, updated_at = now() WHERE id = %s",
        (Json({"stage": stage, "message": message}), job_id),
    )


def used_topics(conn, series_id) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT topic FROM jobs WHERE series_id = %s AND topic IS NOT NULL ORDER BY created_at",
            (series_id,),
        )
        return [r[0] for r in cur.fetchall()]


def _exec(conn, query: str, params: tuple) -> None:
    with conn.cursor() as cur:
        cur.execute(query, params)
    conn.commit()


def insert_finding(conn, series_id, finding: dict[str, Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO research_findings (series_id, topic, claim, paper_title, paper_url)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (
                series_id,
                finding["topic"],
                finding["claim"],
                finding["paper_title"],
                finding["paper_url"],
            ),
        )
        finding_id = cur.fetchone()[0]
    conn.commit()
    return finding_id


def fetch_unused_finding(conn, series_id) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT * FROM research_findings
               WHERE series_id = %s AND used_by_job_id IS NULL
               ORDER BY created_at LIMIT 1""",
            (series_id,),
        )
        return cur.fetchone()


def mark_finding_used(conn, finding_id, job_id) -> None:
    _exec(
        conn,
        "UPDATE research_findings SET used_by_job_id = %s WHERE id = %s",
        (job_id, finding_id),
    )


def count_unused_findings(conn, series_id) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM research_findings WHERE series_id = %s AND used_by_job_id IS NULL",
            (series_id,),
        )
        return cur.fetchone()[0]
