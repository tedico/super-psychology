"""Named visual style presets, assembled per the five-part-formula brief
(medium -> lighting -> palette -> texture, plus positive constraints).

Presets describe concrete visual DNA only — no studio or brand names in
prompt text (works better with image models; keeps a sellable product clean).
Versioned in code until the dashboard phase moves them to the DB.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StylePreset:
    name: str
    medium: str
    lighting: str
    palette: str
    texture: str
    constraints: str


PRESETS: dict[str, StylePreset] = {
    "anime-watercolor": StylePreset(
        name="anime-watercolor",
        medium="hand-drawn 2D anime illustration with cel-shaded characters over watercolor-washed painterly backgrounds",
        lighting="soft diffused natural daylight with gentle golden-hour accents",
        palette="lush greens, sky blues, and warm cream highlights, saturated but gentle",
        texture="visible watercolor paper grain, soft brush edges, painterly cloud and foliage detail",
        constraints="wholesome, serene mood with expressive faces; any background text reads as illegible marks; era-appropriate objects only, no logos",
    ),
    "manga-ink": StylePreset(
        name="manga-ink",
        medium="black-and-white manga ink illustration with screentone shading",
        lighting="high-contrast dramatic inking with bold directional shadow",
        palette="pure monochrome with rich blacks, clean whites, and mid-grey halftones",
        texture="crisp pen linework, halftone screentone dots, subtle paper tooth",
        constraints="expressive faces and dynamic framing; any background text reads as illegible marks; no logos",
    ),
    "muted-editorial": StylePreset(
        name="muted-editorial",
        medium="soft editorial illustration",
        lighting="cinematic single-source key light with soft falloff",
        palette="warm limited palette of muted tones with cream highlights",
        texture="subtle film grain and a matte finish",
        constraints="single clear focal subject; any background text reads as illegible marks; no logos",
    ),
}
