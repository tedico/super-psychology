import base64
import time
from pathlib import Path

import httpx

from sp_worker import costs
from sp_worker.providers.base import MotionResult

BASE = "https://generativelanguage.googleapis.com/v1beta"


class VeoMotion:
    """Image-to-video motion via Google's Veo long-running-operation API.

    Recorded LIVE 2026-07-04 (worker/scripts/smoke_veo.py, commit 3265da1):
    submit POST {model}:predictLongRunning -> {"name": "models/.../operations/<id>"};
    poll GET {name} until done:true; video at
    response.generateVideoResponse.generatedSamples[0].video.uri, downloadable
    via plain GET with the same x-goog-api-key header. durationSeconds MUST be
    sent (API default is 8s, double cost).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
        poll_interval: float = 5.0,
        timeout_s: float = 600,
    ):
        self._key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=600)
        self._poll_interval = poll_interval
        self._timeout_s = timeout_s

    def animate(self, image_path: Path, prompt: str, out_path: Path) -> MotionResult:
        headers = {"x-goog-api-key": self._key}
        image_b64 = base64.b64encode(image_path.read_bytes()).decode()

        resp = self._client.post(
            f"{BASE}/models/{self._model}:predictLongRunning",
            headers=headers,
            json={
                "instances": [{
                    "prompt": prompt,
                    "image": {"bytesBase64Encoded": image_b64, "mimeType": "image/png"},
                }],
                "parameters": {
                    "aspectRatio": "9:16",
                    "durationSeconds": costs.VEO_CLIP_SECONDS,
                },
            },
        )
        resp.raise_for_status()
        op_name = resp.json()["name"]

        deadline = time.monotonic() + self._timeout_s
        op: dict = {}
        while True:
            op = self._client.get(f"{BASE}/{op_name}", headers=headers).json()
            if op.get("done"):
                break
            if time.monotonic() >= deadline:
                elapsed = self._timeout_s
                raise RuntimeError(
                    f"Veo operation {op_name!r} timed out after {elapsed:.0f}s elapsed"
                )
            time.sleep(self._poll_interval)

        try:
            video_uri = op["response"]["generateVideoResponse"]["generatedSamples"][0]["video"][
                "uri"
            ]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"unexpected Veo response shape ({e!r})") from e

        dl = self._client.get(video_uri, headers=headers)
        dl.raise_for_status()
        out_path.write_bytes(dl.content)

        cost = round(costs.VEO_PER_SECOND * costs.VEO_CLIP_SECONDS, 6)
        return MotionResult(clip_path=out_path, cost_usd=cost)
