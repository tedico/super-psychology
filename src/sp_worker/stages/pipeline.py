import time
from pathlib import Path

from sp_worker import repo
from sp_worker.providers.registry import Providers
from sp_worker.stages.assembly import assemble
from sp_worker.stages.research import fetch_research
from sp_worker.stages.script import write_script
from sp_worker.stages.topic import pick_topic
from sp_worker.stages.visuals import generate_images, split_clauses


def run_job(conn, job_id, providers: Providers, media_dir: Path) -> Path:
    """Run all Phase-2 stages for a queued job. Returns the finished mp4 path.

    On any stage failure: marks the job failed with the stage + message, then
    re-raises so the caller (CLI) exits non-zero. SMS alerting arrives with the
    Zo deploy (Phase 5).
    """
    job = repo.fetch_job(conn, job_id)
    series = repo.fetch_series(conn, job["series_id"])
    workdir = media_dir / "jobs" / str(job_id)
    workdir.mkdir(parents=True, exist_ok=True)
    repo.start_job(conn, job_id)

    stage = "research"
    try:
        t0 = time.monotonic()
        finding = fetch_research(conn, series)
        repo.set_stage(conn, job_id, "research", "done", seconds=time.monotonic() - t0)

        stage = "topic"
        t0 = time.monotonic()
        if finding is not None:
            topic = finding.topic  # grounded topic is free — no LLM call
        else:
            topic, cost = pick_topic(
                providers.llm, series["niche_prompt"], repo.used_topics(conn, series["id"])
            )
            repo.add_cost(conn, job_id, cost)
        repo.set_stage(conn, job_id, "topic", "done", seconds=time.monotonic() - t0)

        stage = "script"
        t0 = time.monotonic()
        grounding = (
            f"{finding.claim} (Source: {finding.paper_title})" if finding is not None else None
        )
        script = write_script(providers.llm, topic, series["niche_prompt"], grounding=grounding)
        description = script.description
        if finding is not None:
            description = f"{script.description}\n\nSource: {finding.paper_title} — {finding.paper_url}"
        repo.save_script(
            conn, job_id, topic=topic, script=script.narration, title=script.title,
            description=description, hashtags=script.hashtags,
        )
        if finding is not None:
            repo.mark_finding_used(conn, finding.id, job_id)
        repo.add_cost(conn, job_id, script.cost_usd)
        repo.set_stage(conn, job_id, "script", "done", seconds=time.monotonic() - t0)

        stage = "voiceover"
        t0 = time.monotonic()
        tts = providers.tts.synthesize(script.narration, series["voice_id"], workdir)
        repo.set_asset(conn, job_id, "audio", str(tts.audio_path))
        repo.add_cost(conn, job_id, tts.cost_usd)
        repo.set_stage(conn, job_id, "voiceover", "done", seconds=time.monotonic() - t0)

        stage = "visuals"
        t0 = time.monotonic()
        image_paths, _prompts, img_cost = generate_images(
            providers.images, script.narration, workdir,
            style_preset=series.get("style_preset"),
            visual_style_prompt=series["visual_style_prompt"],
        )
        repo.add_cost(conn, job_id, img_cost)
        repo.set_stage(conn, job_id, "visuals", "done", seconds=time.monotonic() - t0)

        beats = split_clauses(script.narration)

        stage = "motion"
        t0 = time.monotonic()
        motion_clips: list[Path | None] | None = None
        if providers.motion is not None:
            motion_cfg = series.get("motion_config") or {}
            n = min(int(motion_cfg.get("firstNImages", 0)), len(image_paths))
            motion_clips = [None] * len(image_paths)
            for i in range(n):
                clip_path = workdir / f"clip_{i:03d}.mp4"
                clip = providers.motion.animate(
                    image_paths[i], f"subtle cinematic motion: {beats[i]}", clip_path
                )
                motion_clips[i] = clip.clip_path
                repo.set_asset(conn, job_id, f"clip_{i:03d}", str(clip.clip_path))
                repo.add_cost(conn, job_id, clip.cost_usd)
        repo.set_stage(conn, job_id, "motion", "done", seconds=time.monotonic() - t0)

        stage = "assembly"
        t0 = time.monotonic()
        music_path = None
        if providers.music is not None:
            music = providers.music.provide()
            music_path = music.music_path
            repo.set_asset(conn, job_id, "music", str(music_path))
            repo.add_cost(conn, job_id, music.cost_usd)
        video_path = assemble(
            images=image_paths, beats=beats, words=tts.words,
            audio_path=tts.audio_path, out_dir=workdir, music_path=music_path,
            title=script.title, motion_clips=motion_clips,
        )
        repo.set_asset(conn, job_id, "video", str(video_path))
        repo.set_stage(conn, job_id, "assembly", "done", seconds=time.monotonic() - t0)

        repo.finish_job(conn, job_id)
        return video_path
    except Exception as exc:
        conn.rollback()  # clear any aborted transaction so the failure can still be recorded
        repo.fail_job(conn, job_id, stage=stage, message=str(exc))
        raise
