import base64
from pathlib import Path

import httpx

from sp_worker import costs
from sp_worker.providers.base import ImageResult

BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiImage:
    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        self._key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=300)

    def generate(self, prompt: str, out_path: Path) -> ImageResult:
        resp = self._client.post(
            f"{BASE}/models/{self._model}:generateContent",
            headers={"x-goog-api-key": self._key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        resp.raise_for_status()
        try:
            parts = resp.json()["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            raise ValueError(
                f"unexpected Gemini image response shape ({e!r}); possibly safety-filtered"
            ) from e
        for part in parts:
            inline = part.get("inlineData")
            if inline and inline.get("mimeType", "").startswith("image/"):
                out_path.write_bytes(base64.b64decode(inline["data"]))
                return ImageResult(image_path=out_path, cost_usd=costs.GEMINI_PER_IMAGE)
        raise ValueError(f"Gemini reply contained no image part for prompt: {prompt[:80]!r}")
