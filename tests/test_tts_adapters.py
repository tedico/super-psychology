import base64
from pathlib import Path

import httpx
import pytest

from sp_worker.providers.base import WordTiming
from sp_worker.providers.tts_elevenlabs import ElevenLabsTTS, words_from_alignment
from sp_worker.providers.tts_edge import EdgeTTS


def test_words_from_alignment_groups_characters():
    chars = list("hi you")
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    ends = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    words = words_from_alignment(chars, starts, ends)
    assert words == [
        WordTiming(word="hi", start=0.0, end=0.2),
        WordTiming(word="you", start=0.3, end=0.6),
    ]


def test_elevenlabs_synthesize_writes_audio_and_words(tmp_path: Path):
    fake_audio = b"ID3fakemp3bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["xi-api-key"] == "ek"
        assert "text-to-speech/voice-abc/with-timestamps" in str(request.url)
        return httpx.Response(200, json={
            "audio_base64": base64.b64encode(fake_audio).decode(),
            "alignment": {
                "characters": list("hi you"),
                "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
                "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            },
        })

    tts = ElevenLabsTTS(api_key="ek", client=httpx.Client(transport=httpx.MockTransport(handler)))
    r = tts.synthesize("hi you", "voice-abc", tmp_path)
    assert r.audio_path.read_bytes() == fake_audio
    assert r.words[1].word == "you"
    assert r.cost_usd == pytest.approx(6 * 0.00018)


def test_elevenlabs_raises_value_error_when_alignment_missing(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"audio_base64": base64.b64encode(b"x").decode()})

    tts = ElevenLabsTTS(api_key="ek", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError, match="ElevenLabs"):
        tts.synthesize("hi", "voice-abc", tmp_path)


def test_edge_tts_synthesize_collects_word_boundaries(tmp_path: Path, monkeypatch):
    class FakeCommunicate:
        def __init__(self, text, voice, boundary=None):
            # edge-tts >= 7.0 defaults to SentenceBoundary; the adapter MUST
            # request WordBoundary explicitly or word timings silently vanish.
            assert voice == "en-US-GuyNeural"
            assert boundary == "WordBoundary"

        async def stream(self):
            yield {"type": "audio", "data": b"fake"}
            yield {"type": "WordBoundary", "offset": 0, "duration": 3_500_000, "text": "hi"}
            yield {"type": "audio", "data": b"mp3"}
            yield {"type": "WordBoundary", "offset": 4_000_000, "duration": 3_000_000, "text": "you"}

    import sp_worker.providers.tts_edge as edge_mod

    monkeypatch.setattr(edge_mod.edge_tts, "Communicate", FakeCommunicate)
    r = EdgeTTS(voice="en-US-GuyNeural").synthesize("hi you", "ignored-elevenlabs-id", tmp_path)
    assert r.audio_path.read_bytes() == b"fakemp3"
    assert r.words == [
        WordTiming(word="hi", start=0.0, end=0.35),
        WordTiming(word="you", start=0.4, end=0.7),
    ]
    assert r.cost_usd == 0.0
