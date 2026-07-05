from pathlib import Path

import pytest

from sp_worker.providers.music_local import LocalMusic


def test_local_music_returns_existing_file(tmp_path: Path):
    f = tmp_path / "track.mp3"
    f.write_bytes(b"ID3fake")
    r = LocalMusic(f).provide()
    assert r.music_path == f
    assert r.cost_usd == 0.0


def test_local_music_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="music file missing"):
        LocalMusic(tmp_path / "nope.mp3").provide()


def test_local_music_raises_when_path_is_a_directory(tmp_path: Path):
    with pytest.raises(ValueError, match="music file missing"):
        LocalMusic(tmp_path).provide()
