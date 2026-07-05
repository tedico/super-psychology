"""Manual live smoke for the Gemini key + model ids. Run once:
    .venv/bin/python scripts/smoke_gemini.py
Verifies: text model answers; image model returns an image. Prints available
image-capable models if the configured id 404s (then set GEMINI_IMAGE_MODEL in .env).
"""

import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sp_worker.config import Settings
from sp_worker.providers.images_gemini import GeminiImage
from sp_worker.providers.llm_gemini import GeminiLLM


def main() -> int:
    s = Settings()
    if not s.gemini_api_key:
        print("GEMINI_API_KEY missing in worker/.env")
        return 1
    text = GeminiLLM(s.gemini_api_key, s.gemini_text_model).generate("Reply with exactly: pong")
    print(f"text model {s.gemini_text_model}: {text.text.strip()!r} (est ${text.cost_usd})")

    try:
        with tempfile.TemporaryDirectory() as td:
            img = GeminiImage(s.gemini_api_key, s.gemini_image_model).generate(
                "A single orange circle on white background, flat illustration",
                Path(td) / "smoke.png",
            )
            print(f"image model {s.gemini_image_model}: wrote {img.image_path.stat().st_size} bytes")
    except httpx.HTTPStatusError as e:
        print(f"image model {s.gemini_image_model} failed: {e.response.status_code}")
        listing = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": s.gemini_api_key}, params={"pageSize": 50},
        ).json()
        names = [m["name"] for m in listing.get("models", []) if "image" in m["name"].lower()]
        print("image-capable model ids:", *names, sep="\n  ")
        print("Set GEMINI_IMAGE_MODEL=<id without 'models/'> in worker/.env and re-run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
