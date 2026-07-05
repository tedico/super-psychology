import json
from pathlib import Path

import pytest

from sp_worker.stages.pipeline import run_job
from sp_worker import repo
from .fakes import FakeImage, FakeLLM, FakeTTS
from .test_repo import _mk_series

SCRIPT_JSON = json.dumps({
    "narration": "Your brain lies to you. Nobody watches you as closely as you think. "
                 "Psychologists call it the spotlight effect. Remember that next time.",
    "title": "The Spotlight Effect",
    "description": "Why nobody notices your bad hair day.",
    "hashtags": ["#psychology", "#shorts"],
})


@pytest.fixture()
def providers():
    from sp_worker.providers.registry import Providers

    return Providers(
        llm=FakeLLM([json.dumps({"topic": "The spotlight effect"}), SCRIPT_JSON]),
        tts=FakeTTS(),
        images=FakeImage(),
    )


def test_run_job_end_to_end(conn, providers, tmp_path: Path):
    series_id = _mk_series(conn)
    job_id = repo.create_job(conn, series_id)

    out = run_job(conn, job_id, providers, media_dir=tmp_path)

    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "done"
    assert job["topic"] == "The spotlight effect"
    assert job["title"] == "The Spotlight Effect"
    for stage in ("research", "topic", "script", "voiceover", "visuals", "motion", "assembly"):
        assert job["stage_status"][stage]["status"] == "done"
        assert job["stage_status"][stage]["seconds"] >= 0
    # deterministic fakes: topic 0.001 + script 0.001 + tts 0.002 + 4 images x 0.003
    # (4 clauses: split_clauses on the narration above yields 4 punctuation-delimited beats)
    assert float(job["cost_usd"]) == pytest.approx(0.016)
    assert job["asset_paths"]["video"] == str(out)
    assert out.exists()
    assert len(list((tmp_path / "jobs" / str(job_id)).glob("img_*.png"))) == 4
    assert job["asset_paths"]["audio"].endswith("voiceover.wav")
    assert "TitleCard" in (tmp_path / "jobs" / str(job_id) / "captions.ass").read_text()


def test_run_job_records_failure_even_when_transaction_was_aborted(conn, tmp_path: Path):
    import json as _json

    from sp_worker.providers.registry import Providers

    class TxnPoisonTTS:
        def synthesize(self, text, voice_id, out_dir):
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM table_that_does_not_exist")
            except Exception:
                pass  # transaction is now aborted; the connection needs a rollback
            raise RuntimeError("tts exploded after poisoning txn")

    providers = Providers(
        llm=FakeLLM([_json.dumps({"topic": "T"}), SCRIPT_JSON]),
        tts=TxnPoisonTTS(),
        images=FakeImage(),
    )
    series_id = _mk_series(conn)
    job_id = repo.create_job(conn, series_id)

    with pytest.raises(RuntimeError, match="tts exploded"):
        run_job(conn, job_id, providers, media_dir=tmp_path)

    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "failed"
    assert job["error"]["stage"] == "voiceover"


def test_run_job_failure_records_stage_and_reraises(conn, tmp_path: Path):
    from sp_worker.providers.registry import Providers

    class BoomTTS:
        def synthesize(self, text, voice_id, out_dir):
            raise RuntimeError("tts exploded")

    providers = Providers(
        llm=FakeLLM([json.dumps({"topic": "T"}), SCRIPT_JSON]),
        tts=BoomTTS(),
        images=FakeImage(),
    )
    series_id = _mk_series(conn)
    job_id = repo.create_job(conn, series_id)

    with pytest.raises(RuntimeError, match="tts exploded"):
        run_job(conn, job_id, providers, media_dir=tmp_path)

    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "failed"
    assert job["error"]["stage"] == "voiceover"
    assert "tts exploded" in job["error"]["message"]


def test_run_job_grounded_by_research_finding(conn, tmp_path: Path):
    from sp_worker.providers.registry import Providers
    from .test_repo import FINDING

    series_id = _mk_series(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE series SET knowledge_source = 'consensus' WHERE id = %s", (series_id,))
    conn.commit()
    finding_id = repo.insert_finding(conn, series_id, FINDING)
    job_id = repo.create_job(conn, series_id)

    # Only ONE canned LLM response: the script. Grounded topic needs no LLM call.
    providers = Providers(llm=FakeLLM([SCRIPT_JSON]), tts=FakeTTS(), images=FakeImage())
    run_job(conn, job_id, providers, media_dir=tmp_path)

    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "done"
    assert job["topic"] == "The spotlight effect"          # from the finding
    assert FINDING["paper_url"] in job["description"]       # citation appended
    assert job["stage_status"]["research"]["status"] == "done"
    with conn.cursor() as cur:
        cur.execute("SELECT used_by_job_id FROM research_findings WHERE id = %s", (finding_id,))
        assert str(cur.fetchone()[0]) == str(job_id)         # finding consumed


def test_run_job_motion_animates_first_n_images(conn, tmp_path: Path):
    from sp_worker.providers.registry import Providers
    from .fakes import FakeMotion

    providers = Providers(
        llm=FakeLLM([json.dumps({"topic": "T"}), SCRIPT_JSON]),
        tts=FakeTTS(), images=FakeImage(), motion=FakeMotion(),
    )
    series_id = _mk_series(conn)  # motion_config DB default: enabled, firstNImages 2
    job_id = repo.create_job(conn, series_id)
    run_job(conn, job_id, providers, media_dir=tmp_path)

    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "done"
    assert job["stage_status"]["motion"]["status"] == "done"
    assert job["asset_paths"]["clip_000"].endswith("clip_000.mp4")
    assert job["asset_paths"]["clip_001"].endswith("clip_001.mp4")
    assert "clip_002" not in job["asset_paths"]  # guardrail: first 2 only (4 images exist)
    assert float(job["cost_usd"]) == pytest.approx(0.016 + 2 * 0.05)


def test_run_job_with_music_records_asset(conn, tmp_path: Path):
    from sp_worker.providers.music_local import LocalMusic
    from sp_worker.providers.registry import Providers
    from .fakes import _write_sine_wav

    music_file = tmp_path / "bg.wav"
    _write_sine_wav(music_file, seconds=1.0)
    providers = Providers(
        llm=FakeLLM([json.dumps({"topic": "T"}), SCRIPT_JSON]),
        tts=FakeTTS(), images=FakeImage(), music=LocalMusic(music_file),
    )
    series_id = _mk_series(conn)
    job_id = repo.create_job(conn, series_id)
    run_job(conn, job_id, providers, media_dir=tmp_path)
    job = repo.fetch_job(conn, job_id)
    assert job["status"] == "done"
    assert job["asset_paths"]["music"] == str(music_file)
