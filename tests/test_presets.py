import pytest

from sp_worker.stages.presets import PRESETS
from sp_worker.stages.visuals import build_image_prompt


def test_preset_prompt_follows_five_part_order():
    p = PRESETS["anime-watercolor"]
    prompt = build_image_prompt(
        "Your brain lies to you,", style_preset="anime-watercolor", visual_style_prompt="ignored"
    )
    # beat first, composition fixed, then style fields in brief order
    assert prompt.index("Your brain lies to you,") < prompt.index("9:16 vertical")
    assert "center two-thirds" in prompt
    order = [prompt.index(p.medium), prompt.index(p.lighting), prompt.index(p.palette), prompt.index(p.texture)]
    assert order == sorted(order)
    assert prompt.rstrip().endswith(p.constraints + ".")


def test_all_presets_build_and_contain_no_brand_names():
    for name in PRESETS:
        prompt = build_image_prompt("A test beat.", style_preset=name, visual_style_prompt="x")
        assert "ghibli" not in prompt.lower()
        assert "studio" not in prompt.lower()


def test_unknown_preset_raises_value_error():
    with pytest.raises(ValueError, match="unknown style preset"):
        build_image_prompt("beat", style_preset="vaporwave", visual_style_prompt="x")


def test_null_preset_falls_back_to_legacy_prompt():
    legacy = build_image_prompt("A beat here.", style_preset=None, visual_style_prompt="muted editorial illustration")
    assert legacy == (
        'muted editorial illustration. Vertical 9:16 composition. Illustrate this moment from a short '
        'narration: "A beat here.". No text, no words, no captions, no watermarks in the image.'
    )
