import base64
from pathlib import Path

import httpx
import pytest

from sp_worker.providers.images_gemini import GeminiImage

PNG = b"\x89PNG\r\n\x1a\nfakepngbytes"


def test_gemini_image_decodes_inline_data(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gk"
        assert "gemini-2.5-flash-image:generateContent" in str(request.url)
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [
                {"text": "here is your image"},
                {"inlineData": {"mimeType": "image/png",
                                "data": base64.b64encode(PNG).decode()}},
            ]}}],
        })

    img = GeminiImage(api_key="gk", model="gemini-2.5-flash-image",
                      client=httpx.Client(transport=httpx.MockTransport(handler)))
    out = tmp_path / "img_0.png"
    r = img.generate("a brain under a spotlight, editorial illustration", out)
    assert r.image_path.read_bytes() == PNG
    assert r.cost_usd == 0.039


def test_gemini_image_raises_when_no_image_part(tmp_path: Path):
    def handler(request):
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "cannot draw that"}]}}],
        })

    img = GeminiImage(api_key="gk", model="m",
                      client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError, match="no image"):
        img.generate("p", tmp_path / "x.png")


def test_gemini_image_raises_value_error_on_empty_candidates(tmp_path: Path):
    img = GeminiImage(api_key="gk", model="m",
                      client=httpx.Client(transport=httpx.MockTransport(
                          lambda r: httpx.Response(200, json={"candidates": []}))))
    with pytest.raises(ValueError, match="Gemini"):
        img.generate("p", tmp_path / "x.png")
