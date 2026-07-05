import json

import pytest

from sp_worker.stages.jsonutil import extract_json
from sp_worker.stages.script import Script, write_script
from sp_worker.stages.topic import pick_topic
from .fakes import FakeLLM


def test_extract_json_plain_and_fenced():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure!\n```json\n{"a": 1}\n```\nDone.') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_pick_topic_excludes_used_and_returns_topic_with_cost():
    llm = FakeLLM([json.dumps({"topic": "The spotlight effect"})])
    topic, cost = pick_topic(llm, niche_prompt="surprising psychology", used=["Cognitive dissonance"])
    assert topic == "The spotlight effect"
    assert cost == 0.001
    assert "Cognitive dissonance" in llm.prompts[0]
    assert "surprising psychology" in llm.prompts[0]


def test_write_script_returns_script_fields():
    llm = FakeLLM([json.dumps({
        "narration": "First sentence. Second sentence. Third sentence. Fourth sentence.",
        "title": "Why you notice yourself",
        "description": "A short about the spotlight effect.",
        "hashtags": ["#psychology", "#shorts"],
    })])
    s = write_script(llm, topic="The spotlight effect", niche_prompt="surprising psychology")
    assert isinstance(s, Script)
    assert s.narration.startswith("First sentence.")
    assert s.title and s.description and s.hashtags == ["#psychology", "#shorts"]
    assert "The spotlight effect" in llm.prompts[0]


def test_write_script_raises_on_missing_field():
    llm = FakeLLM([json.dumps({"narration": "x", "title": "t", "description": "d"})])
    with pytest.raises(ValueError, match="hashtags"):
        write_script(llm, topic="t", niche_prompt="n")


def test_write_script_includes_grounding_block():
    llm = FakeLLM([json.dumps({
        "narration": "x", "title": "t", "description": "d", "hashtags": ["#a"],
    })])
    write_script(
        llm, topic="The spotlight effect", niche_prompt="psychology",
        grounding="People overestimate attention. Source: Gilovich 1999.",
    )
    assert "People overestimate attention" in llm.prompts[0]
    assert "Do not invent other studies" in llm.prompts[0]
