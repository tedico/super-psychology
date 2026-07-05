from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to the worker/ directory so the service finds .env regardless of CWD
# (Phase 1 review note: env_file=".env" resolved against CWD).
WORKER_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = WORKER_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str

    elevenlabs_api_key: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model ids are env-overridable: verify against ListModels via
    # scripts/smoke_gemini.py and override in .env if the deployed id differs.
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"
    claude_model: str = "claude-sonnet-5"
    edge_tts_voice: str = "en-US-GuyNeural"
    # Verified 2026-07-04 via LIVE discovery (worker/scripts/smoke_veo.py, see
    # commit 3265da1) against Ted's Gemini key: veo-3.1-fast-generate-preview
    # was the working image-to-video model.
    veo_model: str = "veo-3.1-fast-generate-preview"

    media_dir: Path = WORKER_DIR / "data"
