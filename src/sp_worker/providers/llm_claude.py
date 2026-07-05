import httpx

from sp_worker import costs
from sp_worker.providers.base import LLMResult

BASE = "https://api.anthropic.com/v1"


class ClaudeLLM:
    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        self._key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=120)

    def generate(self, prompt: str) -> LLMResult:
        resp = self._client.post(
            f"{BASE}/messages",
            headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
            json={
                "model": self._model,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        except (KeyError, IndexError) as e:
            raise ValueError(
                f"unexpected Claude response shape ({e!r}); possibly safety-filtered"
            ) from e
        if not text.strip():
            raise ValueError("Claude returned no text blocks")
        usage = data.get("usage", {})
        cost = costs.llm_cost(
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            costs.CLAUDE_IN_PER_MTOK,
            costs.CLAUDE_OUT_PER_MTOK,
        )
        return LLMResult(text=text, cost_usd=cost)
