import base64
import json
from pathlib import Path

import httpx
import pytest

from sp_worker.providers.motion_veo import VeoMotion

PNG = b"\x89PNG\r\n\x1a\nfakepngbytes"
MP4 = b"\x00fakemp4"
OP_NAME = "models/veo-3.1-fast-generate-preview/operations/op-123"
FILE_URI = "https://generativelanguage.googleapis.com/download/v1beta/files/abc123:download"


def _write_png(tmp_path: Path) -> Path:
    p = tmp_path / "src.png"
    p.write_bytes(PNG)
    return p


def _stateful_handler(poll_count: dict):
    """Simulate: submit -> op name; first 2 GET polls -> done:false;
    3rd poll -> done:true with recorded response shape; GET file uri -> mp4 bytes.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "test-key"

        if request.method == "POST" and "predictLongRunning" in str(request.url):
            body = json.loads(request.content)
            instance = body["instances"][0]
            assert body["parameters"]["durationSeconds"] == 4
            assert body["parameters"]["aspectRatio"] == "9:16"
            assert instance["image"]["bytesBase64Encoded"] == base64.b64encode(PNG).decode()
            assert instance["prompt"] == "gentle drifting clouds"
            return httpx.Response(200, json={"name": OP_NAME})

        if request.method == "GET" and str(request.url).endswith(OP_NAME):
            poll_count["n"] += 1
            if poll_count["n"] < 3:
                return httpx.Response(200, json={"name": OP_NAME, "done": False})
            return httpx.Response(
                200,
                json={
                    "name": OP_NAME,
                    "done": True,
                    "response": {
                        "generateVideoResponse": {
                            "generatedSamples": [{"video": {"uri": FILE_URI}}]
                        }
                    },
                },
            )

        if request.method == "GET" and str(request.url) == FILE_URI:
            return httpx.Response(200, content=MP4)

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


def test_veo_animate_happy_path_downloads_clip_and_reports_cost(tmp_path: Path):
    poll_count = {"n": 0}
    client = httpx.Client(transport=httpx.MockTransport(_stateful_handler(poll_count)))
    img_path = _write_png(tmp_path)
    out_path = tmp_path / "clip_000.mp4"

    motion = VeoMotion(
        api_key="test-key",
        model="veo-3.1-fast-generate-preview",
        client=client,
        poll_interval=0,
    )
    result = motion.animate(img_path, "gentle drifting clouds", out_path)

    assert out_path.read_bytes() == MP4
    assert result.clip_path == out_path
    assert result.cost_usd == pytest.approx(0.40)
    assert poll_count["n"] == 3


def test_veo_raises_value_error_on_malformed_done_response(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"name": OP_NAME})
        if request.method == "GET":
            return httpx.Response(200, json={"name": OP_NAME, "done": True, "response": {}})
        raise AssertionError("unexpected request")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    img_path = _write_png(tmp_path)
    motion = VeoMotion(api_key="k", model="m", client=client, poll_interval=0)

    with pytest.raises(ValueError, match="Veo"):
        motion.animate(img_path, "p", tmp_path / "out.mp4")


def test_veo_raises_http_status_error_on_submit_500(tmp_path: Path):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(500, text="server error"))
    )
    img_path = _write_png(tmp_path)
    motion = VeoMotion(api_key="k", model="m", client=client, poll_interval=0)

    with pytest.raises(httpx.HTTPStatusError):
        motion.animate(img_path, "p", tmp_path / "out.mp4")


def test_veo_raises_runtime_error_on_timeout(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"name": OP_NAME})
        if request.method == "GET":
            return httpx.Response(200, json={"name": OP_NAME, "done": False})
        raise AssertionError("unexpected request")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    img_path = _write_png(tmp_path)
    motion = VeoMotion(api_key="k", model="m", client=client, poll_interval=0, timeout_s=0.001)

    with pytest.raises(RuntimeError, match="(?i)timeout|elapsed"):
        motion.animate(img_path, "p", tmp_path / "out.mp4")
