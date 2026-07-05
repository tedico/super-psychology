import math
import shutil
import struct
import wave
from pathlib import Path

from sp_worker.providers.base import ImageResult, LLMResult, TTSResult, WordTiming

FIXTURES = Path(__file__).parent / "fixtures"


class FakeLLM:
    """Returns queued canned responses; records prompts."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> LLMResult:
        self.prompts.append(prompt)
        return LLMResult(text=self._responses.pop(0), cost_usd=0.001)


class FakeTTS:
    """Writes a real, valid WAV of sine-wave audio; timings spread evenly."""

    def synthesize(self, text: str, voice_id: str, out_dir: Path) -> TTSResult:
        words = text.split()
        per_word = 0.35
        duration = max(1.0, per_word * len(words))
        audio_path = out_dir / "voiceover.wav"
        _write_sine_wav(audio_path, seconds=duration)
        timings = [
            WordTiming(word=w, start=round(i * per_word, 3), end=round((i + 1) * per_word, 3))
            for i, w in enumerate(words)
        ]
        return TTSResult(audio_path=audio_path, words=timings, cost_usd=0.002)


class FakeImage:
    """Copies a checked-in 8x8 PNG fixture to the requested path."""

    def generate(self, prompt: str, out_path: Path) -> ImageResult:
        shutil.copy(FIXTURES / "pixel.png", out_path)
        return ImageResult(image_path=out_path, cost_usd=0.003)


class FakeMotion:
    """Writes a real 1s animated clip via ffmpeg lavfi; deterministic cost."""

    def animate(self, image_path: Path, prompt: str, out_path: Path):
        import subprocess

        from sp_worker.providers.base import MotionResult

        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "color=c=red:s=540x960:d=1,hue='h=2*PI*t*20:s=1'",
             "-pix_fmt", "yuv420p", str(out_path)],
            capture_output=True, check=True,
        )
        return MotionResult(clip_path=out_path, cost_usd=0.05)


def _write_sine_wav(path: Path, seconds: float, rate: int = 22050) -> None:
    n = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(n)
        )
        w.writeframes(frames)
