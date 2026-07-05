from pathlib import Path

from sp_worker.stages.visuals import generate_images, split_clauses
from .fakes import FakeImage


def test_split_clauses_breaks_on_all_punctuation():
    text = "Your brain lies to you, constantly. Nobody watches you as closely as you think! Why is that? Because everyone is busy: managing themselves."
    assert split_clauses(text) == [
        "Your brain lies to you,",
        "constantly. Nobody watches you as closely as you think!",
        "Why is that?",
        "Because everyone is busy:",
        "managing themselves.",
    ]


def test_split_clauses_merges_short_fragments():
    # "constantly." is under 3 words -> merges into the following clause
    text = "Your brain lies to you, constantly. Psychologists call it the spotlight effect."
    assert split_clauses(text) == [
        "Your brain lies to you,",
        "constantly. Psychologists call it the spotlight effect.",
    ]


def test_split_clauses_merges_short_leading_fragment():
    text = "Wait. Nobody is actually watching you at all."
    assert split_clauses(text) == ["Wait. Nobody is actually watching you at all."]


def test_split_clauses_preserves_word_count():
    text = "One, two. Three! Four? Five: six; seven eight nine."
    clauses = split_clauses(text)
    assert " ".join(clauses).split() == text.split()


def test_generate_images_one_file_per_clause_and_sums_cost(tmp_path: Path):
    fake = FakeImage()
    narration = "First fact here, with a twist. Second fact stands alone. Third fact, believe it or not, has three clauses."
    paths, prompts, cost = generate_images(
        fake, narration, tmp_path, visual_style_prompt="muted editorial illustration"
    )
    clauses = split_clauses(narration)
    assert len(paths) == len(clauses)
    assert all(p.exists() for p in paths)
    assert paths[0].name == "img_000.png"
    assert "muted editorial illustration" in prompts[0]
    assert clauses[0] in prompts[0]
    assert "text" in prompts[0].lower()
    assert cost == round(0.003 * len(clauses), 6)
