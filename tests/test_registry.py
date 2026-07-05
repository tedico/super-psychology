import pytest

from sp_worker.config import Settings
from sp_worker.providers.images_gemini import GeminiImage
from sp_worker.providers.llm_claude import ClaudeLLM
from sp_worker.providers.llm_gemini import GeminiLLM
from sp_worker.providers.registry import build_providers
from sp_worker.providers.tts_edge import EdgeTTS
from sp_worker.providers.tts_elevenlabs import ElevenLabsTTS


def _settings(**kw):
    defaults = dict(
        database_url="postgres://u:p@localhost/km",
        elevenlabs_api_key="ek", gemini_api_key="gk",
        anthropic_api_key="ak",
    )
    defaults.update(kw)
    return Settings(_env_file=None, **defaults)


def test_premium_config_builds_premium_adapters():
    cfg = {"llm": "claude", "tts": "elevenlabs", "images": "nano-banana-2"}
    p = build_providers(cfg, _settings())
    assert isinstance(p.llm, ClaudeLLM)
    assert isinstance(p.tts, ElevenLabsTTS)
    assert isinstance(p.images, GeminiImage)


def test_budget_config_builds_budget_adapters():
    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    p = build_providers(cfg, _settings())
    assert isinstance(p.llm, GeminiLLM)
    assert isinstance(p.tts, EdgeTTS)
    assert isinstance(p.images, GeminiImage)


def test_missing_key_raises_actionable_error():
    cfg = {"llm": "claude", "tts": "elevenlabs", "images": "nano-banana-2"}
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_providers(cfg, _settings(anthropic_api_key=None))


def test_unknown_provider_name_raises():
    with pytest.raises(ValueError, match="unknown llm provider"):
        build_providers({"llm": "gpt9", "tts": "edge", "images": "pexels"}, _settings())


def test_removed_pexels_provider_raises():
    cfg = {"llm": "gemini", "tts": "edge", "images": "pexels"}
    with pytest.raises(ValueError, match="unknown images provider"):
        build_providers(cfg, _settings())


def test_music_config_builds_local_music():
    from sp_worker.config import WORKER_DIR
    from sp_worker.providers.music_local import LocalMusic

    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    music_cfg = {"enabled": True, "path": "assets/music/China Dreaming.mp3"}
    p = build_providers(cfg, _settings(), music_config=music_cfg)
    assert isinstance(p.music, LocalMusic)
    assert p.music._path == WORKER_DIR / "assets/music/China Dreaming.mp3"


def test_music_disabled_or_absent_builds_none():
    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    assert build_providers(cfg, _settings()).music is None
    assert build_providers(cfg, _settings(), music_config={"enabled": False, "path": "x"}).music is None


def test_music_empty_path_builds_none():
    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    music_cfg = {"enabled": True, "path": ""}
    assert build_providers(cfg, _settings(), music_config=music_cfg).music is None


def test_motion_config_enabled_builds_veo_motion():
    from sp_worker.providers.motion_veo import VeoMotion

    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    motion_cfg = {"enabled": True, "firstNImages": 2}
    p = build_providers(cfg, _settings(), motion_config=motion_cfg)
    assert isinstance(p.motion, VeoMotion)
    assert p.motion._model == _settings().veo_model


def test_motion_disabled_or_absent_or_zero_n_builds_none():
    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    assert build_providers(cfg, _settings()).motion is None
    assert build_providers(
        cfg, _settings(), motion_config={"enabled": False, "firstNImages": 2}
    ).motion is None
    assert build_providers(
        cfg, _settings(), motion_config={"enabled": True, "firstNImages": 0}
    ).motion is None


def test_motion_enabled_missing_gemini_key_raises_actionable_error():
    cfg = {"llm": "gemini", "tts": "edge", "images": "nano-banana-2"}
    motion_cfg = {"enabled": True, "firstNImages": 2}
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_providers(cfg, _settings(gemini_api_key=None), motion_config=motion_cfg)
