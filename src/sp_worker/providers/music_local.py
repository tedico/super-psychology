from pathlib import Path

from sp_worker.providers.base import MusicResult


class LocalMusic:
    """Budget/default music tier: a fixed local track, zero cost.

    Premium tier (ElevenLabs Music, per-series generated tracks) is a later
    phase — requires flipping Music Generation access on the ElevenLabs key.
    """

    def __init__(self, path: Path):
        self._path = path

    def provide(self) -> MusicResult:
        if not self._path.is_file():
            raise ValueError(f"music file missing: {self._path}")
        return MusicResult(music_path=self._path, cost_usd=0.0)
