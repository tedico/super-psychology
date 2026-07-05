"""Manual LIVE smoke for Veo image-to-video on Ted's Gemini key. Run once:
    PYTHONPATH=src .venv/bin/python scripts/smoke_veo.py
Discovers: available veo model ids; a working generate call (image -> clip);
exact request/response shape; latency; bytes; verified cost basis.
Its printed output is AUTHORITATIVE over the plan's candidate shape.
"""

import base64
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sp_worker.config import Settings

BASE = "https://generativelanguage.googleapis.com/v1beta"
# 4s keeps 2 clips/video at $0.80 on veo-3.1-fast ($0.10/s @720p) — under the $1.50 gate.
DURATION_S = 4


def find_video_refs(node, path=""):
    """Walk the done-operation response for any video uri / inline bytes fields."""
    refs = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            if k in ("uri", "videoUri", "url") and isinstance(v, str):
                refs.append((p, "uri", v))
            elif k == "bytesBase64Encoded" and isinstance(v, str):
                refs.append((p, "b64", v))
            else:
                refs.extend(find_video_refs(v, p))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            refs.extend(find_video_refs(v, f"{path}[{i}]"))
    return refs


def main() -> int:
    s = Settings()
    if not s.gemini_api_key:
        print("GEMINI_API_KEY missing")
        return 1
    headers = {"x-goog-api-key": s.gemini_api_key}
    client = httpx.Client(timeout=600)

    # 1) list video-capable models
    listing = client.get(f"{BASE}/models", headers=headers, params={"pageSize": 100}).json()
    veo_models = [m["name"] for m in listing.get("models", []) if "veo" in m["name"].lower()]
    print("veo model ids:", *veo_models or ["<none — Veo may need allowlist/billing tier>"], sep="\n  ")
    if not veo_models:
        return 1
    # prefer a fast/cheap variant if present, else first listed
    preferred = [m for m in veo_models if "fast" in m.lower()]
    model = (preferred or veo_models)[0].removeprefix("models/")
    print(f"\nusing: {model}")

    # 2) tiny source image via ffmpeg (no repo assets consumed)
    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "src.png"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=orange:s=540x960:d=1",
             "-frames:v", "1", str(img)], capture_output=True, check=True)
        img_b64 = base64.b64encode(img.read_bytes()).decode()

        # 3) candidate request shape (CORRECT ME from the real API's errors):
        t0 = time.monotonic()
        resp = client.post(
            f"{BASE}/models/{model}:predictLongRunning",
            headers=headers,
            json={
                "instances": [{
                    "prompt": "gentle drifting clouds, soft camera push-in, serene",
                    "image": {"bytesBase64Encoded": img_b64, "mimeType": "image/png"},
                }],
                "parameters": {"aspectRatio": "9:16", "durationSeconds": DURATION_S},
            },
        )
        print("submit status:", resp.status_code)
        print("submit body (first 800):", resp.text[:800])
        resp.raise_for_status()
        op_name = resp.json()["name"]

        # 4) poll
        polls = 0
        while True:
            op = client.get(f"{BASE}/{op_name}", headers=headers).json()
            polls += 1
            if op.get("done"):
                break
            time.sleep(5)
        elapsed = time.monotonic() - t0
        print(f"operation done in {elapsed:.0f}s ({polls} polls)")
        if "error" in op:
            print("operation ERROR:", op["error"])
            return 1
        print("response keys:", list(op.get("response", {}).keys()))
        redacted = str(op.get("response"))
        print("full response (first 1200):", redacted[:1200])

        # 5) download the produced video and ffprobe it
        refs = find_video_refs(op.get("response", {}))
        print("\nvideo refs found:")
        for p, kind, v in refs:
            print(f"  {p} ({kind}): {v[:120] if kind == 'uri' else f'<{len(v)} b64 chars>'}")
        if not refs:
            print("NO video refs found — inspect response above.")
            return 1

        clip = Path(td) / "clip.mp4"
        path0, kind, val = refs[0]
        if kind == "b64":
            clip.write_bytes(base64.b64decode(val))
        else:
            dl = client.get(val, headers=headers, follow_redirects=True)
            print("download status:", dl.status_code, "bytes:", len(dl.content))
            dl.raise_for_status()
            clip.write_bytes(dl.content)
        print(f"clip written: {clip.stat().st_size} bytes (from {path0})")

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,avg_frame_rate:format=duration",
             "-of", "default=noprint_wrappers=1", str(clip)],
            capture_output=True, text=True)
        print("ffprobe:\n" + probe.stdout + probe.stderr)

    print("\nNOW RECORD: model id, request shape corrections, response video field path,")
    print("clip duration/resolution, latency, and pricing from ai.google.dev/pricing for this model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
