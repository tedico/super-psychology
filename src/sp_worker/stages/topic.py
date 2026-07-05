from sp_worker.providers.base import LLMProvider
from sp_worker.stages.jsonutil import extract_json

PROMPT = """You pick the next topic for a faceless short-video series.

Niche: {niche}

Topics already covered (do NOT repeat or closely paraphrase any of these):
{used}

Pick ONE new, specific, hook-friendly topic for the next 60-90 second video.
Reply with JSON only: {{"topic": "<the topic>"}}"""


def pick_topic(llm: LLMProvider, niche_prompt: str, used: list[str]) -> tuple[str, float]:
    """Returns (topic, cost_usd)."""
    used_block = "\n".join(f"- {t}" for t in used) if used else "- (none yet)"
    result = llm.generate(PROMPT.format(niche=niche_prompt, used=used_block))
    data = extract_json(result.text)
    topic = data.get("topic", "").strip()
    if not topic:
        raise ValueError("LLM returned empty topic")
    return topic, result.cost_usd
