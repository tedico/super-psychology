import httpx

from sp_worker import costs
from sp_worker.providers.base import LLMResult

BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiLLM:
    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None):
        self._key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=120)

    def generate(self, prompt: str) -> LLMResult:
        resp = self._client.post(
            f"{BASE}/models/{self._model}:generateContent",
            headers={"x-goog-api-key": self._key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise ValueError(
                f"unexpected Gemini response shape ({e!r}); possibly safety-filtered"
            ) from e
        if not text.strip():
            raise ValueError("Gemini returned empty text")
        usage = data.get("usageMetadata", {})
        cost = costs.llm_cost(
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
            costs.GEMINI_TEXT_IN_PER_MTOK,
            costs.GEMINI_TEXT_OUT_PER_MTOK,
        )
        return LLMResult(text=text, cost_usd=cost)
