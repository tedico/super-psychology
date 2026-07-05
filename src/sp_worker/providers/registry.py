from dataclasses import dataclass
from pathlib import Path

from sp_worker.config import WORKER_DIR, Settings
from sp_worker.providers.base import (
    ImageProvider,
    LLMProvider,
    MotionProvider,
    MusicProvider,
    TTSProvider,
)
from sp_worker.providers.images_gemini import GeminiImage
from sp_worker.providers.llm_claude import ClaudeLLM
from sp_worker.providers.llm_gemini import GeminiLLM
from sp_worker.providers.motion_veo import VeoMotion
from sp_worker.providers.music_local import LocalMusic
from sp_worker.providers.tts_edge import EdgeTTS
from sp_worker.providers.tts_elevenlabs import ElevenLabsTTS


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    tts: TTSProvider
    images: ImageProvider
    music: MusicProvider | None = None
    motion: MotionProvider | None = None


def _require(value: str | None, env_name: str) -> str:
    if not value:
        raise RuntimeError(
            f"{env_name} is not set in worker/.env — required by this series' providerConfig"
        )
    return value


def build_providers(
    provider_config: dict,
    settings: Settings,
    music_config: dict | None = None,
    motion_config: dict | None = None,
) -> Providers:
    llm_name = provider_config.get("llm", "claude")
    tts_name = provider_config.get("tts", "elevenlabs")
    images_name = provider_config.get("images", "nano-banana-2")

    if llm_name == "claude":
        llm = ClaudeLLM(_require(settings.anthropic_api_key, "ANTHROPIC_API_KEY"),
                        settings.claude_model)
    elif llm_name == "gemini":
        llm = GeminiLLM(_require(settings.gemini_api_key, "GEMINI_API_KEY"),
                        settings.gemini_text_model)
    else:
        raise ValueError(f"unknown llm provider: {llm_name!r}")

    if tts_name == "elevenlabs":
        tts = ElevenLabsTTS(_require(settings.elevenlabs_api_key, "ELEVENLABS_API_KEY"))
    elif tts_name == "edge":
        tts = EdgeTTS(voice=settings.edge_tts_voice)
    else:
        raise ValueError(f"unknown tts provider: {tts_name!r}")

    if images_name == "nano-banana-2":
        images = GeminiImage(_require(settings.gemini_api_key, "GEMINI_API_KEY"),
                             settings.gemini_image_model)
    else:
        raise ValueError(f"unknown images provider: {images_name!r}")

    music: MusicProvider | None = None
    if music_config and music_config.get("enabled") and music_config.get("path"):
        music_path = Path(music_config.get("path", ""))
        if not music_path.is_absolute():
            music_path = WORKER_DIR / music_path
        music = LocalMusic(music_path)

    motion: MotionProvider | None = None
    if motion_config and motion_config.get("enabled") and motion_config.get("firstNImages"):
        motion = VeoMotion(_require(settings.gemini_api_key, "GEMINI_API_KEY"), settings.veo_model)

    return Providers(llm=llm, tts=tts, images=images, music=music, motion=motion)
