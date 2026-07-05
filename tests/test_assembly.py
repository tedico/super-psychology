import json
import subprocess
from pathlib import Path

from sp_worker.providers.base import WordTiming
from sp_worker.stages.assembly import assemble, build_ass, image_durations
from .fakes import FakeImage, FakeTTS

WORDS = [
    WordTiming("First", 0.0, 0.3), WordTiming("fact.", 0.35, 0.6),
    WordTiming("Second", 0.7, 1.0), WordTiming("fact.", 1.05, 1.3),
    WordTiming("Third", 1.4, 1.7), WordTiming("fact.", 1.75, 2.0),
]


def test_image_durations_from_word_timings():
    # 2 beats: "First fact. Second fact." (4 words) and "Third fact." (2 words)
    beats = ["First fact. Second fact.", "Third fact."]
    durations = image_durations(beats, WORDS, total=2.5)
    # beat 1 ends at end of its last word (1.3); beat 2 runs to total
    assert durations == [1.3, 1.2]


def test_build_ass_groups_words_into_caption_events():
    ass = build_ass(WORDS, max_words=2)
    assert "[Script Info]" in ass and "PlayResX: 1080" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:00.60,Caption,,0,0,0,,First fact." in ass
    assert "Dialogue: 0,0:00:00.70,0:00:01.30,Caption,,0,0,0,,Second fact." in ass


def test_build_ffmpeg_cmd_escapes_colons_in_subtitle_path(tmp_path: Path):
    from sp_worker.stages.assembly import build_ffmpeg_cmd

    ass = tmp_path / "a:b" / "captions.ass"
    cmd = build_ffmpeg_cmd([tmp_path / "i.png"], [1.0], tmp_path / "a.wav", ass, tmp_path / "o.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "a\\:b" in fc
    assert f"subtitles={ass}" not in fc  # unescaped form must be gone


def test_build_ass_strips_ass_override_braces():
    from sp_worker.providers.base import WordTiming
    from sp_worker.stages.assembly import build_ass

    words = [WordTiming("{weird}", 0.0, 0.3), WordTiming("word", 0.4, 0.6)]
    ass = build_ass(words, max_words=2)
    assert "{weird}" not in ass
    assert "weird word" in ass


def test_assemble_renders_real_mp4(tmp_path: Path):
    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    img_paths = [
        FakeImage().generate("p", tmp_path / f"img_{i:03d}.png").image_path for i in range(2)
    ]
    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]
    out = assemble(
        images=img_paths, beats=beats, words=tts.words,
        audio_path=tts.audio_path, out_dir=tmp_path,
    )
    assert out.exists() and out.suffix == ".mp4"
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout)
    kinds = {s["codec_type"] for s in probe["streams"]}
    assert kinds == {"video", "audio"}
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1080, 1920)
    assert float(probe["format"]["duration"]) > 1.5


def _solid_png(path: Path, color: str) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x64:d=1",
         "-frames:v", "1", str(path)],
        capture_output=True, check=True,
    )
    return path


def _mean_rgb(video: Path, t: float) -> tuple[float, float, float]:
    raw = subprocess.run(
        ["ffmpeg", "-ss", str(t), "-i", str(video), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    n = len(raw) // 3
    return (sum(raw[0::3]) / n, sum(raw[1::3]) / n, sum(raw[2::3]) / n)


def test_assemble_switches_images_at_beat_boundaries(tmp_path: Path):
    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    img_paths = [
        _solid_png(tmp_path / "img_000.png", "red"),
        _solid_png(tmp_path / "img_001.png", "blue"),
    ]
    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]
    # cta_text=None: this test is about beat switching; the outro fade would
    # dim the t=2.2 probe (outro behavior is covered by the outro tests).
    out = assemble(images=img_paths, beats=beats, words=tts.words,
                   audio_path=tts.audio_path, out_dir=tmp_path, cta_text=None)
    # beat 1 covers ~0-1.4s, beat 2 ~1.4-2.8s; probe mid-beat
    r1 = _mean_rgb(out, 0.7)
    r2 = _mean_rgb(out, 2.2)
    assert r1[0] > r1[2] + 50, f"expected red-dominant frame at t=0.7, got {r1}"
    assert r2[2] > r2[0] + 50, f"expected blue-dominant frame at t=2.2, got {r2}"


def test_build_ffmpeg_cmd_adds_ducked_music_when_present(tmp_path: Path):
    from sp_worker.stages.assembly import build_ffmpeg_cmd

    cmd = build_ffmpeg_cmd(
        [tmp_path / "i.png"], [1.0], tmp_path / "a.wav", tmp_path / "c.ass",
        tmp_path / "o.mp4", music_path=tmp_path / "m.mp3",
    )
    joined = " ".join(cmd)
    assert "-stream_loop -1" in joined
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "sidechaincompress" in fc
    assert "amix" in fc
    assert "[aout]" in fc
    assert cmd[cmd.index("-map") + 3] == "[aout]"  # second -map targets the mixed audio


def test_build_ffmpeg_cmd_no_music_maps_raw_voice(tmp_path: Path):
    from sp_worker.stages.assembly import build_ffmpeg_cmd

    cmd = build_ffmpeg_cmd(
        [tmp_path / "i.png"], [1.0], tmp_path / "a.wav", tmp_path / "c.ass", tmp_path / "o.mp4"
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "sidechaincompress" not in fc
    assert cmd[cmd.index("-map") + 3] == "1:a"  # one image -> audio is input index 1


def test_build_ffmpeg_cmd_motion_clip_replaces_zoompan_for_that_slot(tmp_path: Path):
    from sp_worker.stages.assembly import build_ffmpeg_cmd

    clip_a = tmp_path / "clipA.mp4"
    img_a = tmp_path / "imgA.png"
    img_b = tmp_path / "imgB.png"

    cmd = build_ffmpeg_cmd(
        [img_a, img_b], [1.5, 1.3], tmp_path / "a.wav", tmp_path / "c.ass",
        tmp_path / "o.mp4", motion_clips=[clip_a, None],
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    filters = fc.split(";")

    slot0 = next(f for f in filters if f.startswith("[0:v]"))
    slot1 = next(f for f in filters if f.startswith("[1:v]"))

    assert "trim=duration=1.500" in slot0
    assert "setpts=PTS-STARTPTS" in slot0
    assert "zoompan" not in slot0

    assert "zoompan" in slot1
    assert "trim=" not in slot1

    # slot 0's input is a plain "-i clip" with no -loop/-t before it
    i_flag_idx = cmd.index("-i")
    assert cmd[i_flag_idx] == "-i"
    assert cmd[i_flag_idx + 1] == str(clip_a)
    assert cmd[i_flag_idx - 1] != "-loop"
    assert cmd[i_flag_idx - 1] != "-t"

    # bookkeeping: voice index unaffected — still len(images) inputs before audio
    voice_idx = len([img_a, img_b])
    assert cmd[cmd.index("-map") + 3] == f"{voice_idx}:a"


def _lavfi_clip(path: Path, seconds: float = 3.0) -> Path:
    # testsrc2's mean-RGB is flat over time by design (a full-spectrum test
    # pattern that scrolls but self-cancels in the spatial mean — its motion
    # is real per-pixel, but a whole-frame mean-RGB probe can't see it, even
    # composed with a hue rotation). Use a hue-rotating solid-color source
    # instead: genuinely animated content generated via ffmpeg lavfi whose
    # mean-RGB drifts strongly and deterministically frame to frame, which is
    # what the pixel-probe assertions below need to detect real motion.
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c=red:s=540x960:d={seconds},hue='h=2*PI*t*20:s=1'",
         "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True,
    )
    return path


def _rgb_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def test_assemble_plays_motion_clip_for_clip_bearing_beat(tmp_path: Path):
    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    clip_a = _lavfi_clip(tmp_path / "clipA.mp4", seconds=3.0)
    img_a = tmp_path / "imgA.png"  # unused visually (motion clip replaces it) but still an image slot
    img_b = _solid_png(tmp_path / "img_001.png", "green")
    _solid_png(img_a, "red")  # placeholder image for beat 1 slot; motion clip supersedes it

    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]
    # cta_text=None: this test is about motion clips and voice-length duration;
    # the outro is covered by the dedicated outro tests.
    out = assemble(
        images=[img_a, img_b], beats=beats, words=tts.words,
        audio_path=tts.audio_path, out_dir=tmp_path, motion_clips=[clip_a, None],
        cta_text=None,
    )

    assert out.exists()

    # two frames INSIDE beat 1 (beat 1 spans ~0-1.4s) must differ strongly — real motion.
    f1 = _mean_rgb(out, 0.3)
    f2 = _mean_rgb(out, 1.1)
    assert _rgb_distance(f1, f2) > 30, f"expected strong difference, got {f1} vs {f2}"

    # beat 2 (~1.4-2.8s) is the solid green image.
    g = _mean_rgb(out, 2.2)
    assert g[1] > g[0] + 30 and g[1] > g[2] + 30, f"expected green-dominant frame at t=2.2, got {g}"

    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout)
    assert abs(float(probe["format"]["duration"]) - 2.8) < 0.4  # still voice-length

    ass_text = (tmp_path / "captions.ass").read_text()
    assert "Dialogue:" in ass_text


def test_assemble_with_music_renders_and_is_louder(tmp_path: Path):
    import re
    import subprocess

    def mean_volume(video: Path) -> float:
        proc = subprocess.run(
            ["ffmpeg", "-i", str(video), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        match = re.search(r"mean_volume: (-?\d+\.?\d*) dB", proc.stderr)
        assert match, proc.stderr[-500:]
        return float(match.group(1))

    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    imgs = [FakeImage().generate("p", tmp_path / f"img_{i:03d}.png").image_path for i in range(2)]
    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]

    # cta_text=None on both renders: this test is about the music mix and that
    # music must not extend the voice-length duration; outro tests cover the CTA.
    silent_dir = tmp_path / "no_music"
    silent_dir.mkdir()
    plain = assemble(images=imgs, beats=beats, words=tts.words,
                     audio_path=tts.audio_path, out_dir=silent_dir, cta_text=None)

    music = tmp_path / "music.wav"
    from .fakes import _write_sine_wav

    _write_sine_wav(music, seconds=1.0)  # loops via -stream_loop
    with_music_dir = tmp_path / "with_music"
    with_music_dir.mkdir()
    mixed = assemble(images=imgs, beats=beats, words=tts.words,
                     audio_path=tts.audio_path, out_dir=with_music_dir, music_path=music,
                     cta_text=None)

    import json as _json

    for video in (plain, mixed):
        probe = _json.loads(subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video)],
            capture_output=True, text=True, check=True).stdout)
        assert abs(float(probe["format"]["duration"]) - 2.8) < 0.4  # voice-length, music didn't extend it

    assert mean_volume(mixed) > mean_volume(plain)  # music energy present under the voice


def _ffprobe_format(video: Path) -> dict:
    return json.loads(subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout)["format"]


def _bright_pixel_count(video: Path, t: float, threshold: int = 200) -> int:
    # Count near-white pixels in the frame at time t (all three channels bright).
    raw = subprocess.run(
        ["ffmpeg", "-ss", str(t), "-i", str(video), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return sum(
        1 for i in range(0, len(raw) - 2, 3)
        if raw[i] > threshold and raw[i + 1] > threshold and raw[i + 2] > threshold
    )


def test_assemble_outro_extends_and_fades(tmp_path: Path):
    # CTA is ON by default: video gains a 3.5s card after the voice ends.
    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    imgs = [_solid_png(tmp_path / "img_000.png", "red"),
            _solid_png(tmp_path / "img_001.png", "blue")]
    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]
    out = assemble(images=imgs, beats=beats, words=tts.words,
                   audio_path=tts.audio_path, out_dir=tmp_path)  # CTA on by default
    fmt = _ffprobe_format(out)
    assert abs(float(fmt["duration"]) - (2.8 + 3.5)) < 0.5  # voice + CTA_TOTAL_S
    # mid-CTA frame: near-black background with bright CTA text pixels
    cta = _mean_rgb(out, 2.8 + 1.8)
    assert max(cta) < 90, f"expected dark CTA frame, got {cta}"
    assert _bright_pixel_count(out, 2.8 + 1.8) > 200, "expected CTA text pixels on the card"
    # fade-out: a frame near the end of the content is much darker than an
    # earlier frame of the same (blue) beat
    late = _mean_rgb(out, 2.6)
    early = _mean_rgb(out, 1.6)
    assert sum(late) < sum(early) * 0.55, f"expected fade-out, got late={late} early={early}"


def test_assemble_cta_none_keeps_voice_length(tmp_path: Path):
    # cta_text=None disables the outro entirely: old duration semantics, no fade.
    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    imgs = [_solid_png(tmp_path / "img_000.png", "red"),
            _solid_png(tmp_path / "img_001.png", "blue")]
    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]
    out = assemble(images=imgs, beats=beats, words=tts.words,
                   audio_path=tts.audio_path, out_dir=tmp_path, cta_text=None)
    fmt = _ffprobe_format(out)
    assert abs(float(fmt["duration"]) - 2.8) < 0.4  # voice-length only
    # no fade-out: late frame in the blue beat stays as bright as an earlier one
    late = _mean_rgb(out, 2.6)
    early = _mean_rgb(out, 1.6)
    assert sum(late) > sum(early) * 0.8, f"unexpected fade, got late={late} early={early}"
    # and no Outro event in the ASS file
    assert ",Outro," not in (tmp_path / "captions.ass").read_text()


def test_build_ass_title_card_event_centered_opaque():
    from sp_worker.stages.assembly import build_ass

    words = [WordTiming("hello", 0.0, 0.4), WordTiming("world", 0.5, 0.9)]
    ass = build_ass(words, title="The Birthday Paradox: 23 People, 50% Chance", title_end=2.75)
    # style exists: opaque box (BorderStyle 3), middle-center (Alignment 5)
    style_line = next(l for l in ass.splitlines() if l.startswith("Style: TitleCard"))
    fields = [f.strip() for f in style_line.split(",")]
    assert fields[7] == "3"   # BorderStyle: opaque box
    assert fields[10] == "5"  # Alignment: middle-center
    # event runs 0 -> title_end on layer 1
    assert "Dialogue: 1,0:00:00.00,0:00:02.75,TitleCard,,0,0,0,,The Birthday Paradox: 23 People, 50% Chance" in ass
    # captions unchanged
    assert "Dialogue: 0,0:00:00.00,0:00:00.90,Caption,,0,0,0,,hello world" in ass


def test_build_ass_title_truncated_to_100_chars_and_sanitized():
    from sp_worker.stages.assembly import build_ass

    words = [WordTiming("x", 0.0, 0.3)]
    long_title = "A" * 130
    ass = build_ass(words, title=long_title + "{override}\nnewline", title_end=1.0)
    line = next(l for l in ass.splitlines() if ",TitleCard," in l)
    text = line.split(",TitleCard,,0,0,0,,")[1]
    assert len(text) <= 100
    assert "{" not in text and "}" not in text and "\n" not in text


def test_build_ass_without_title_has_no_titlecard_event():
    from sp_worker.stages.assembly import build_ass

    words = [WordTiming("x", 0.0, 0.3)]
    ass = build_ass(words)
    assert ",TitleCard," not in ass


def test_assemble_title_card_shows_then_disappears(tmp_path: Path):
    # red first beat, blue second; card should brighten the center of beat 1 only
    tts = FakeTTS().synthesize("First fact. Second fact. Third fact. Fourth fact.", "v", tmp_path)
    imgs = [
        _solid_png(tmp_path / "img_000.png", "red"),
        _solid_png(tmp_path / "img_001.png", "blue"),
    ]
    beats = ["First fact. Second fact.", "Third fact. Fourth fact."]
    # cta_text=None: this test is about the title card; the outro fade would
    # dim the t=2.2 "plain blue" probe (outro is covered by the outro tests).
    out = assemble(images=imgs, beats=beats, words=tts.words,
                   audio_path=tts.audio_path, out_dir=tmp_path, title="A Great Hook Title",
                   cta_text=None)

    def center_mean_rgb(video: Path, t: float) -> tuple[float, float, float]:
        raw = subprocess.run(
            ["ffmpeg", "-ss", str(t), "-i", str(video), "-frames:v", "1",
             "-vf", "crop=540:400:270:760",  # central region
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, check=True,
        ).stdout
        n = len(raw) // 3
        return (sum(raw[0::3]) / n, sum(raw[1::3]) / n, sum(raw[2::3]) / n)

    during = center_mean_rgb(out, 0.7)   # mid beat 1: white card over red
    after = center_mean_rgb(out, 2.2)    # mid beat 2: plain blue, no card
    # card present: green+blue channels lifted well above pure red's near-zero
    assert during[1] > 60 and during[2] > 60, f"expected card whiteness at t=0.7, got {during}"
    # card gone: back to blue-dominant, red/green low
    assert after[2] > after[0] + 50 and after[1] < 60, f"expected plain blue at t=2.2, got {after}"
