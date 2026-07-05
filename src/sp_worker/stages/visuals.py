import re
from pathlib import Path

from sp_worker.providers.base import ImageProvider
from sp_worker.stages.presets import PRESETS

# Ted's pacing rule (2026-07-04): every punctuation-delimited clause is a scene —
# a new image. Fragments under MIN_CLAUSE_WORDS merge into a neighbor so "Yes."
# doesn't burn an image. AutoShorts-style ~3-4s cuts.
CLAUSE_BOUNDARY = re.compile(r"(?<=[.!?,;:])\s+")
MIN_CLAUSE_WORDS = 3

PROMPT_TEMPLATE = (
    "{style}. Vertical 9:16 composition. Illustrate this moment from a short "
    "narration: \"{beat}\". No text, no words, no captions, no watermarks in the image."
)

COMPOSITION = (
    "Medium shot, 9:16 vertical composition, subject occupying the center two-thirds of the frame"
)

PRESET_TEMPLATE = (
    "Illustrate this moment from a short narration: \"{beat}\". {composition}. "
    "Style: {medium}; {lighting}; {palette}; {texture}. {constraints}."
)


def build_image_prompt(beat: str, style_preset: str | None, visual_style_prompt: str) -> str:
    if style_preset is None:
        return PROMPT_TEMPLATE.format(style=visual_style_prompt, beat=beat)
    preset = PRESETS.get(style_preset)
    if preset is None:
        raise ValueError(f"unknown style preset: {style_preset!r}")
    return PRESET_TEMPLATE.format(
        beat=beat, composition=COMPOSITION, medium=preset.medium,
        lighting=preset.lighting, palette=preset.palette,
        texture=preset.texture, constraints=preset.constraints,
    )


def split_clauses(narration: str) -> list[str]:
    """Clause-level beats. Invariant relied on by assembly's image_durations:
    " ".join(split_clauses(text)).split() == text.split() — punctuation stays
    attached to words, so per-beat word counts align with TTS word timings.

    Short fragments (under MIN_CLAUSE_WORDS) merge forward into the next
    clause so "Wait." doesn't burn its own image; a short trailing fragment
    with no next clause to join is kept standalone."""
    parts = [p.strip() for p in CLAUSE_BOUNDARY.split(narration.strip()) if p.strip()]
    merged: list[str] = []
    buffer = ""
    last_index = len(parts) - 1
    for i, part in enumerate(parts):
        combined = f"{buffer} {part}".strip() if buffer else part
        if len(combined.split()) < MIN_CLAUSE_WORDS and i != last_index:
            buffer = combined
        else:
            merged.append(combined)
            buffer = ""
    return merged


def generate_images(
    images: ImageProvider,
    narration: str,
    out_dir: Path,
    *,
    style_preset: str | None = None,
    visual_style_prompt: str = "",
) -> tuple[list[Path], list[str], float]:
    """Returns (image_paths, prompts_used, total_cost_usd) — one image per clause."""
    beats = split_clauses(narration)
    paths: list[Path] = []
    prompts: list[str] = []
    total = 0.0
    for i, beat in enumerate(beats):
        prompt = build_image_prompt(beat, style_preset, visual_style_prompt)
        out_path = out_dir / f"img_{i:03d}.png"
        result = images.generate(prompt, out_path)
        paths.append(result.image_path)
        prompts.append(prompt)
        total = round(total + result.cost_usd, 6)
    return paths, prompts, total
