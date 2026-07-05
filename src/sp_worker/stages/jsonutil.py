import json
import re


def extract_json(text: str) -> dict:
    """Parse a JSON object from an LLM reply — bare or inside a ```json fence."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"no JSON object found in LLM reply: {text[:200]!r}")
