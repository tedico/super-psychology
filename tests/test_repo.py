import uuid

from sp_worker import repo


def _mk_series(conn, **overrides):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, 'x') RETURNING id",
            (f"t-{uuid.uuid4().hex}@example.com",),  # unique per call: users.email is UNIQUE
        )
        user_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO series (user_id, name, niche_prompt, voice_id, visual_style_prompt)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (
                user_id,
                overrides.get("name", "Interesting Psychology"),
                overrides.get("niche_prompt", "surprising psychology findings"),
                overrides.get("voice_id", "voice-1"),
                overrides.get("visual_style_prompt", "muted editorial illustration"),
            ),
        )
        series_id = cur.fetchone()[0]
    conn.commit()
    return series_id


def test_create_and_fetch_job_with_series(conn):
    series_id = _mk_series(conn)
    job_id = repo.create_job(conn, series_id)
    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "queued"
    series = repo.fetch_series(conn, job["series_id"])
    assert series["name"] == "Interesting Psychology"
    assert series["provider_config"]["llm"] == "claude"  # DB default applied


def test_stage_bookkeeping_and_costs(conn):
    series_id = _mk_series(conn)
    job_id = repo.create_job(conn, series_id)
    repo.start_job(conn, job_id)
    repo.set_stage(conn, job_id, "topic", "done", seconds=1.2)
    repo.add_cost(conn, job_id, 0.0123)
    repo.add_cost(conn, job_id, 0.0100)
    repo.save_script(
        conn, job_id, topic="Cognitive dissonance", script="Two sentences. Here.",
        title="T", description="D", hashtags=["#psych"],
    )
    repo.set_asset(conn, job_id, "audio", "/tmp/a.mp3")
    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "running"
    assert job["stage_status"]["topic"] == {"status": "done", "seconds": 1.2}
    assert float(job["cost_usd"]) == 0.0223
    assert job["topic"] == "Cognitive dissonance"
    assert job["asset_paths"]["audio"] == "/tmp/a.mp3"


def test_finish_and_fail(conn):
    series_id = _mk_series(conn)
    ok = repo.create_job(conn, series_id)
    repo.finish_job(conn, ok)
    assert repo.fetch_job(conn, ok)["status"] == "done"

    bad = repo.create_job(conn, series_id)
    repo.fail_job(conn, bad, stage="voiceover", message="boom")
    job = repo.fetch_job(conn, bad)
    assert job["status"] == "failed"
    assert job["error"] == {"stage": "voiceover", "message": "boom"}


def test_used_topics_excludes_other_series(conn):
    s1 = _mk_series(conn)
    s2 = _mk_series(conn, name="Other")
    j1 = repo.create_job(conn, s1)
    repo.save_script(conn, j1, topic="Topic A", script="s", title="t", description="d", hashtags=[])
    j2 = repo.create_job(conn, s2)
    repo.save_script(conn, j2, topic="Topic B", script="s", title="t", description="d", hashtags=[])
    assert repo.used_topics(conn, s1) == ["Topic A"]


FINDING = {
    "topic": "The spotlight effect",
    "claim": "People overestimate how much others notice their appearance and behavior.",
    "paper_title": "The Spotlight Effect and the Illusion of Transparency",
    "paper_url": "https://consensus.app/papers/details/example",
}


def test_insert_and_fetch_unused_finding_fifo(conn):
    series_id = _mk_series(conn)
    f1 = repo.insert_finding(conn, series_id, FINDING)
    repo.insert_finding(conn, series_id, {**FINDING, "topic": "Second topic"})
    row = repo.fetch_unused_finding(conn, series_id)
    assert row["id"] == f1
    assert row["topic"] == "The spotlight effect"
    assert repo.count_unused_findings(conn, series_id) == 2


def test_mark_finding_used_removes_it_from_unused(conn):
    series_id = _mk_series(conn)
    finding_id = repo.insert_finding(conn, series_id, FINDING)
    job_id = repo.create_job(conn, series_id)
    repo.mark_finding_used(conn, finding_id, job_id)
    assert repo.fetch_unused_finding(conn, series_id) is None
    assert repo.count_unused_findings(conn, series_id) == 0


def test_unused_findings_scoped_per_series(conn):
    s1 = _mk_series(conn)
    s2 = _mk_series(conn, name="Other")
    repo.insert_finding(conn, s1, FINDING)
    assert repo.fetch_unused_finding(conn, s2) is None


def test_deleting_job_resurrects_its_finding(conn):
    # DECISION (2026-07-04, brief "Decisions made overnight"): used_by_job_id is
    # ON DELETE SET NULL — deleting a job disowns its outputs, returning the
    # finding to the unused pool, consistent with topic dedup freeing a deleted
    # job's topic. Job rows are permanent history; deletion is deliberate.
    series_id = _mk_series(conn)
    finding_id = repo.insert_finding(conn, series_id, FINDING)
    job_id = repo.create_job(conn, series_id)
    repo.mark_finding_used(conn, finding_id, job_id)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    conn.commit()
    row = repo.fetch_unused_finding(conn, series_id)
    assert row is not None
    assert row["id"] == finding_id
