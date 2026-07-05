import base64
from pathlib import Path

import httpx

from sp_worker import costs
from sp_worker.providers.base import TTSResult, WordTiming

BASE = "https://api.elevenlabs.io/v1"


def words_from_alignment(chars: list[str], starts: list[float], ends: list[float]) -> list[WordTiming]:
    words: list[WordTiming] = []
    current = ""
    w_start = 0.0
    w_end = 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if current:
                words.append(WordTiming(word=current, start=w_start, end=w_end))
                current = ""
            continue
        if not current:
            w_start = s
        current += ch
        w_end = e
    if current:
        words.append(WordTiming(word=current, start=w_start, end=w_end))
    return words


class ElevenLabsTTS:
    def __init__(self, api_key: str, model_id: str = "eleven_multilingual_v2",
                 client: httpx.Client | None = None):
        self._key = api_key
        self._model_id = model_id
        self._client = client or httpx.Client(timeout=300)

    def synthesize(self, text: str, voice_id: str, out_dir: Path) -> TTSResult:
        resp = self._client.post(
            f"{BASE}/text-to-speech/{voice_id}/with-timestamps",
            headers={"xi-api-key": self._key},
            params={"output_format": "mp3_44100_128"},
            json={"text": text, "model_id": self._model_id},
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            audio_b64 = data["audio_base64"]
            al = data["alignment"]
            chars = al["characters"]
            starts = al["character_start_times_seconds"]
            ends = al["character_end_times_seconds"]
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"unexpected ElevenLabs response shape ({e!r}); alignment or audio missing"
            ) from e
        audio_path = out_dir / "voiceover.mp3"
        audio_path.write_bytes(base64.b64decode(audio_b64))
        words = words_from_alignment(chars, starts, ends)
        return TTSResult(
            audio_path=audio_path,
            words=words,
            cost_usd=round(len(text) * costs.ELEVENLABS_PER_CHAR, 6),
        )
