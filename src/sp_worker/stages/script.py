from dataclasses import dataclass

from sp_worker.providers.base import LLMProvider
from sp_worker.stages.jsonutil import extract_json

PROMPT = """Write a faceless YouTube-Shorts/Reels narration script.

Niche: {niche}
Topic: {topic}

Rules:
- 150-220 words (60-90 seconds spoken), short punchy sentences.
- Open with a hook in the first sentence; end with a snappy takeaway.
- No stage directions, no emojis, no "welcome back" filler — narration text only.

Reply with JSON only:
{{"narration": "<the full narration>",
  "title": "<catchy video title, max 90 chars>",
  "description": "<1-2 sentence description>",
  "hashtags": ["#...", "#...", "#..."]}}"""

REQUIRED = ("narration", "title", "description", "hashtags")

GROUNDING_TEMPLATE = """

Ground the narration in this real research finding — the claim must drive the script:
Finding: {grounding}
Do not invent other studies, numbers, or sources; any "research shows" phrasing must refer to this finding. Paraphrase naturally for spoken narration — never quote the paper title verbatim in the script."""


@dataclass(frozen=True)
class Script:
    narration: str
    title: str
    description: str
    hashtags: list[str]
    cost_usd: float


def write_script(
    llm: LLMProvider, topic: str, niche_prompt: str, grounding: str | None = None
) -> Script:
    prompt = PROMPT.format(niche=niche_prompt, topic=topic)
    if grounding:
        prompt += GROUNDING_TEMPLATE.format(grounding=grounding)
    result = llm.generate(prompt)
    data = extract_json(result.text)
    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        raise ValueError(f"script JSON missing fields: {', '.join(missing)}")
    return Script(
        narration=data["narration"].strip(),
        title=data["title"].strip(),
        description=data["description"].strip(),
        hashtags=list(data["hashtags"]),
        cost_usd=result.cost_usd,
    )
