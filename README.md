# 🧠 Super Psychology

## What & why

**Why this exists:** Ted runs a psychology Instagram channel (Super
Psychology) that needs a steady supply of research-backed short-form videos
— and per the engines-never-shared rule, no channel may borrow another
project's production engine at runtime.

**What it solves:** turns one psychology paper into one 30-second vertical
video (script → voiceover → images → motion → captions → music bed) without
Ted hand-producing anything. It is the channel's **own** engine — cloned
from the KontentMaschine worker on 2026-07-05, then free to diverge; zero
runtime coupling to KontentMaschine remains. Research comes from
[Alexandria](https://github.com/tedico/alexandria), the shared paper shelf,
via a copied one-file adapter — this repo consumes the shelf, it never
maintains its own research collection.

**Where it fits:** Alexandria (research) → this repo (production) → the
Super Psychology IG channel (distribution).

## Constraints

- **Engine is a clone, not a link** — divergence from KontentMaschine is
  expected and fine; never re-import its code at runtime.
- **Research in, video out** — papers come from Alexandria's Papers DB
  (copied adapter `src/sp_worker/alexandria_client.py`); when a video ships,
  stamp the paper `Used By: Super Psychology` so other channels don't
  double-burn it.
- **Postgres job queue** — jobs/findings live in a local Postgres (schema in
  `migrations/`, cloned from the same source).
- **Output is 9:16 short-form video** with burned captions and title cards.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && pip install pytest
cp .env.example .env   # DATABASE_URL + ELEVENLABS/GEMINI/ANTHROPIC keys
createdb superpsychology            # prod-ish local db
createdb superpsychology_test       # test db (tests apply migrations/)
```

## Usage

```bash
python -m sp_worker.cli ...   # same CLI surface as the source engine
python -m pytest              # 94 tests; DB tests need local Postgres
```

Posting queue for finished videos: `~/SuperPsychology-post-queue/` (manual
posting for now; first three videos staged there).

## How it works

```
Alexandria Papers DB ──copied adapter──▶ topic/research stage
      ▲                                        │
      └── mark_used("Super Psychology") ◀── ship
Pipeline: topic → research → script → visuals → assembly → video.mp4
Providers: Gemini/Claude (LLM), Gemini (images), ElevenLabs/edge (TTS),
Veo (motion), local music bed
```

- `src/sp_worker/stages/` — the five pipeline stages
- `src/sp_worker/providers/` — swappable model/audio providers
- `src/sp_worker/alexandria_client.py` — COPY of Alexandria's adapter (see
  its docstring for copy provenance and re-copy rules)
- `migrations/` — Postgres schema (jobs, research_findings, posts, series)

## Configuration

- `.env` — `DATABASE_URL`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`,
  `ANTHROPIC_API_KEY` (never committed — gitleaks pre-commit + GitHub push
  protection active). For Alexandria reads add `NOTION_API_KEY` +
  `ALEXANDRIA_PAPERS_DB_ID`.
- `data/` — job artifacts and rendered output (gitignored)
- `assets/music/` — **gitignored**: drop royalty-free music beds here
  locally; audio files are never redistributed via this public repo (most
  royalty-free licenses permit use in videos, not redistribution of the
  track). The series config's `music.path` points at a file in here.

## Troubleshooting

- **DB tests error out** — local Postgres not running or
  `superpsychology_test` missing; tests rebuild schema from `migrations/`
  each session.
- **`ModuleNotFoundError: sp_worker`** — run `pip install -e .` in the venv.
- **Provider auth failures** — the engine reuses Ted's existing keys; check
  `.env` against `.env.example`.

## Legend

- **The shelf** — Alexandria's Papers DB (shared research)
- **Stamp** — marking a paper `Used By: Super Psychology` on ship
- **Job** — one video production run (a row in `jobs`)
- **Finding** — one research fact a video is grounded on
