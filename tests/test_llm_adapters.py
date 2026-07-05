import json

import httpx
import pytest

from sp_worker.providers.llm_claude import ClaudeLLM
from sp_worker.providers.llm_gemini import GeminiLLM


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_generate_parses_text_and_estimates_cost():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gk"
        assert "gemini-2.5-flash:generateContent" in str(request.url)
        body = json.loads(request.content)
        assert body["contents"][0]["parts"][0]["text"] == "hi"
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "hello back"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
        })

    llm = GeminiLLM(api_key="gk", model="gemini-2.5-flash", client=_client(handler))
    r = llm.generate("hi")
    assert r.text == "hello back"
    assert r.cost_usd == pytest.approx((10 * 0.30 + 20 * 2.50) / 1_000_000)


def test_gemini_raises_on_http_error():
    llm = GeminiLLM(api_key="gk", model="m", client=_client(lambda r: httpx.Response(500, text="err")))
    with pytest.raises(httpx.HTTPStatusError):
        llm.generate("hi")


def test_claude_generate_parses_text_and_estimates_cost():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "ck"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["model"] == "claude-sonnet-5"
        assert body["messages"][0]["content"] == "hi"
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "hello from claude"}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        })

    llm = ClaudeLLM(api_key="ck", model="claude-sonnet-5", client=_client(handler))
    r = llm.generate("hi")
    assert r.text == "hello from claude"
    assert r.cost_usd == pytest.approx((10 * 3.00 + 20 * 15.00) / 1_000_000)


def test_gemini_raises_value_error_on_empty_candidates():
    llm = GeminiLLM(api_key="gk", model="m",
                    client=_client(lambda r: httpx.Response(200, json={"candidates": []})))
    with pytest.raises(ValueError, match="Gemini"):
        llm.generate("hi")


def test_claude_raises_value_error_when_no_text_blocks():
    handler = lambda r: httpx.Response(200, json={
        "content": [{"type": "tool_use", "id": "x", "name": "n", "input": {}}],
        "usage": {"input_tokens": 5, "output_tokens": 5},
    })
    llm = ClaudeLLM(api_key="ck", model="m", client=_client(handler))
    with pytest.raises(ValueError, match="Claude"):
        llm.generate("hi")
