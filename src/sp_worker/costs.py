"""Per-call cost estimates in USD. ALL VALUES ARE ESTIMATES (medium confidence,
recorded 2026-07-03) so jobs.cost_usd is populated and comparable across runs —
not billing-accurate. Refine against real invoices.
"""

GEMINI_TEXT_IN_PER_MTOK = 0.30
GEMINI_TEXT_OUT_PER_MTOK = 2.50
CLAUDE_IN_PER_MTOK = 3.00
CLAUDE_OUT_PER_MTOK = 15.00
ELEVENLABS_PER_CHAR = 0.00018
GEMINI_PER_IMAGE = 0.039
EDGE_TTS_PER_CHAR = 0.0

# verified 2026-07-04 against ai.google.dev/gemini-api/docs/pricing (720p fast tier)
VEO_PER_SECOND = 0.10
VEO_CLIP_SECONDS = 4


def llm_cost(in_tokens: int, out_tokens: int, in_rate: float, out_rate: float) -> float:
    return round((in_tokens * in_rate + out_tokens * out_rate) / 1_000_000, 6)
