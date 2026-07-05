import wave
from pathlib import Path

from sp_worker.providers.base import WordTiming
from .fakes import FIXTURES, FakeImage, FakeTTS


def test_fake_tts_writes_valid_wav_and_timings(tmp_path: Path):
    r = FakeTTS().synthesize("hello brave new world", "v", tmp_path)
    with wave.open(str(r.audio_path)) as w:
        assert w.getnframes() > 0
    assert r.words[0] == WordTiming(word="hello", start=0.0, end=0.35)
    assert r.words[-1].word == "world"


def test_fake_image_copies_fixture(tmp_path: Path):
    out = tmp_path / "img.png"
    r = FakeImage().generate("a prompt", out)
    assert r.image_path.read_bytes() == (FIXTURES / "pixel.png").read_bytes()
