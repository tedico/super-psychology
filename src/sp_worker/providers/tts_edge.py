import asyncio
from pathlib import Path

import edge_tts

from sp_worker.providers.base import TTSResult, WordTiming

TICKS_PER_SECOND = 10_000_000  # edge-tts offsets/durations are 100ns ticks


class EdgeTTS:
    """Free budget TTS. Ignores the series' (ElevenLabs) voice_id and uses the
    configured edge voice instead."""

    def __init__(self, voice: str):
        self._voice = voice

    def synthesize(self, text: str, voice_id: str, out_dir: Path) -> TTSResult:
        audio, words = asyncio.run(self._run(text))
        audio_path = out_dir / "voiceover.mp3"
        audio_path.write_bytes(audio)
        return TTSResult(audio_path=audio_path, words=words, cost_usd=0.0)

    async def _run(self, text: str) -> tuple[bytes, list[WordTiming]]:
        # boundary= is required: edge-tts >= 7.0 defaults to SentenceBoundary,
        # which would silently break word-level caption timing.
        communicate = edge_tts.Communicate(text, self._voice, boundary="WordBoundary")
        audio = b""
        words: list[WordTiming] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / TICKS_PER_SECOND
                end = start + chunk["duration"] / TICKS_PER_SECOND
                words.append(WordTiming(word=chunk["text"], start=round(start, 3), end=round(end, 3)))
        return audio, words
