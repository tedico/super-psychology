from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class LLMResult:
    text: str
    cost_usd: float


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float  # seconds
    end: float


@dataclass(frozen=True)
class TTSResult:
    audio_path: Path
    words: list[WordTiming]
    cost_usd: float


@dataclass(frozen=True)
class ImageResult:
    image_path: Path
    cost_usd: float


@dataclass(frozen=True)
class MusicResult:
    music_path: Path
    cost_usd: float


@dataclass(frozen=True)
class MotionResult:
    clip_path: Path
    cost_usd: float


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> LLMResult: ...


class TTSProvider(Protocol):
    def synthesize(self, text: str, voice_id: str, out_dir: Path) -> TTSResult: ...


class ImageProvider(Protocol):
    def generate(self, prompt: str, out_path: Path) -> ImageResult: ...


class MusicProvider(Protocol):
    def provide(self) -> MusicResult: ...


class MotionProvider(Protocol):
    def animate(self, image_path: Path, prompt: str, out_path: Path) -> MotionResult: ...
