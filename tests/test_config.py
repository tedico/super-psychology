import pytest
from pydantic import ValidationError

from sp_worker.config import Settings


def test_settings_reads_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/km")
    s = Settings()
    assert s.database_url == "postgres://u:p@localhost:5432/km"


def test_settings_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_env_file_is_anchored_to_repo_root():
    from pathlib import Path

    from sp_worker.config import ENV_FILE, WORKER_DIR

    assert Path(ENV_FILE) == Path(WORKER_DIR) / ".env"
    assert Path(ENV_FILE).is_absolute()
    assert (Path(WORKER_DIR) / "pyproject.toml").exists()  # anchored at repo root


def test_optional_api_keys_default_to_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/km")
    for var in ("ELEVENLABS_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.elevenlabs_api_key is None
    assert s.gemini_api_key is None
    assert s.anthropic_api_key is None


def test_media_dir_defaults_under_repo(monkeypatch):
    from pathlib import Path

    from sp_worker.config import WORKER_DIR

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/km")
    s = Settings(_env_file=None)
    assert Path(s.media_dir) == Path(WORKER_DIR) / "data"


def test_veo_model_default_and_env_overridable():
    s = Settings(_env_file=None, database_url="postgres://u:p@localhost:5432/km")
    assert s.veo_model == "veo-3.1-fast-generate-preview"

    s2 = Settings(
        _env_file=None,
        veo_model="x",
        database_url="postgres://u:p@localhost:5432/km",
    )
    assert s2.veo_model == "x"
