import os
import shutil
import subprocess
from pathlib import Path

from sp_worker.providers.base import WordTiming

FPS = 25
WIDTH, HEIGHT = 1080, 1920

# Outro (Ted's spec, 2026-07-04): content fades out over its last 3s, then a
# black CTA card fades in (1s) and holds for 3.5s total.
OUTRO_FADE_S = 3.0
CTA_FADE_IN_S = 1.0
CTA_TOTAL_S = 3.5
DEFAULT_CTA = "Thanks for watching — subscribe for more"

# The Homebrew `ffmpeg` formula ships without libass (no `subtitles`/`ass`
# filter — see formula caveats); `ffmpeg-full` has it but is keg-only so it
# isn't on PATH. Prefer an explicit override, then a libass-capable build if
# present, then whatever `ffmpeg` resolves to on PATH.
_FFMPEG_FULL_KEG = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")


def _ffmpeg_bin() -> str:
    override = os.environ.get("KM_FFMPEG_BIN")
    if override:
        return override
    if _FFMPEG_FULL_KEG.exists():
        return str(_FFMPEG_FULL_KEG)
    return shutil.which("ffmpeg") or "ffmpeg"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Caption,Arial,88,&H00FFFFFF,&H00000000,&H80000000,-1,1,4,0,2,60,60,320
Style: TitleCard,Arial,96,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,3,14,0,5,80,80,0
Style: Outro,Arial,72,&H00FFFFFF,&H00000000,&H00000000,-1,1,0,0,5,80,80,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

TITLE_MAX_CHARS = 100  # Ted's spec (2026-07-04)


def _ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _sanitize_ass_text(text: str) -> str:
    return text.replace("{", "").replace("}", "").replace("\n", " ")


def build_ass(
    words: list[WordTiming], max_words: int = 3,
    title: str | None = None, title_end: float | None = None,
    cta_text: str | None = None, cta_start: float | None = None,
    cta_end: float | None = None,
) -> str:
    lines = [ASS_HEADER]
    if title and title_end:
        card = _sanitize_ass_text(title)
        if len(card) > TITLE_MAX_CHARS:
            card = card[: TITLE_MAX_CHARS - 3].rstrip() + "..."
        lines.append(
            f"Dialogue: 1,{_ass_time(0.0)},{_ass_time(title_end)},TitleCard,,0,0,0,,{card}"
        )
    if cta_text and cta_start is not None and cta_end is not None:
        cta = _sanitize_ass_text(cta_text)
        lines.append(
            f"Dialogue: 1,{_ass_time(cta_start)},{_ass_time(cta_end)},Outro,,0,0,0,,{cta}"
        )
    for i in range(0, len(words), max_words):
        chunk = words[i : i + max_words]
        text = " ".join(_sanitize_ass_text(w.word) for w in chunk)
        lines.append(
            f"Dialogue: 0,{_ass_time(chunk[0].start)},{_ass_time(chunk[-1].end)},"
            f"Caption,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def image_durations(beats: list[str], words: list[WordTiming], total: float) -> list[float]:
    """Each image covers the words of its beat; the last runs to the audio end."""
    durations: list[float] = []
    cursor = 0
    boundary_prev = 0.0
    for i, beat in enumerate(beats):
        n_words = len(beat.split())
        cursor += n_words
        if i == len(beats) - 1:
            boundary = total
        else:
            boundary = words[min(cursor, len(words)) - 1].end
        durations.append(round(boundary - boundary_prev, 3))
        boundary_prev = boundary
    return durations


def _escape_filter_path(path: Path) -> str:
    # ffmpeg filter args parse ':' as an option separator, ',' as a filter
    # separator, ''' as a quote delimiter, and '\' as escape
    return (
        str(path)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("'", "\\'")
    )


def build_ffmpeg_cmd(
    images: list[Path], durations: list[float], audio_path: Path, ass_path: Path,
    out_path: Path, music_path: Path | None = None,
    motion_clips: list[Path | None] | None = None,
    cta_text: str | None = None,
) -> list[str]:
    cmd: list[str] = [_ffmpeg_bin(), "-y"]
    for i, img in enumerate(images):
        clip = motion_clips[i] if motion_clips else None
        if clip is not None:
            cmd += ["-i", str(clip)]
        else:
            cmd += ["-i", str(img)]
    cmd += ["-i", str(audio_path)]
    voice_idx = len(images)
    if music_path is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]
    if cta_text:
        # Black CTA card segment appended after the content.
        cta_idx = voice_idx + (2 if music_path is not None else 1)
        cmd += [
            "-f", "lavfi",
            "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:d={CTA_TOTAL_S}:r={FPS}",
        ]
    filters = []
    for i, dur in enumerate(durations):
        clip = motion_clips[i] if motion_clips else None
        if clip is not None:
            filters.append(
                f"[{i}:v]trim=duration={dur:.3f},"
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},fps={FPS},setpts=PTS-STARTPTS[v{i}]"
            )
        else:
            frames = max(1, int(dur * FPS))
            filters.append(
                f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},"
                f"zoompan=z='min(zoom+0.0008,1.12)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}[v{i}]"
            )
    concat_inputs = "".join(f"[v{i}]" for i in range(len(durations)))
    filters.append(f"{concat_inputs}concat=n={len(durations)}:v=1:a=0[vc]")
    total = sum(durations)
    fade_start = max(0.0, total - OUTRO_FADE_S)
    fade_dur = total - fade_start
    if cta_text:
        # Content fades to black over its last OUTRO_FADE_S seconds, the CTA
        # card fades in, and subtitles render AFTER the concat so the Outro
        # ASS event lands on the black segment.
        filters.append(f"[vc]fade=t=out:st={fade_start:.3f}:d={fade_dur:.3f}[vcfaded]")
        filters.append(
            f"[{cta_idx}:v]fade=t=in:st=0:d={CTA_FADE_IN_S}[cta]"
        )
        filters.append("[vcfaded][cta]concat=n=2:v=1:a=0[vfull]")
        filters.append(f"[vfull]subtitles={_escape_filter_path(ass_path)}[vout]")
    else:
        filters.append(f"[vc]subtitles={_escape_filter_path(ass_path)}[vout]")
    if music_path is not None:
        music_idx = voice_idx + 1
        # Music sits at low volume and ducks harder whenever the voice speaks.
        filters.append(f"[{voice_idx}:a]asplit=2[vo][sc]")
        filters.append(f"[{music_idx}:a]volume=0.25[bg]")
        filters.append(
            "[bg][sc]sidechaincompress=threshold=0.02:ratio=12:attack=5:release=250[duckbg]"
        )
        filters.append(
            "[vo][duckbg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        audio_map = "[aout]"
    else:
        audio_map = f"{voice_idx}:a"
    if cta_text:
        # Audio fades with the video, then pads silence under the CTA card.
        # The mixed [aout] (or raw voice) gets the same fade window.
        audio_src = audio_map if audio_map.startswith("[") else f"[{audio_map}]"
        filters.append(
            f"{audio_src}afade=t=out:st={fade_start:.3f}:d={fade_dur:.3f},"
            f"apad=pad_dur={CTA_TOTAL_S}[afinal]"
        )
        audio_map = "[afinal]"
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", audio_map,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac",
    ]
    if cta_text:
        # Explicit output duration replaces -shortest: the padded audio and
        # appended card would otherwise fight over where the file ends.
        cmd += ["-t", f"{total + CTA_TOTAL_S:.3f}"]
    else:
        cmd += ["-shortest"]
    cmd += [str(out_path)]
    return cmd


def assemble(
    images: list[Path], beats: list[str], words: list[WordTiming],
    audio_path: Path, out_dir: Path, music_path: Path | None = None,
    title: str | None = None,
    motion_clips: list[Path | None] | None = None,
    cta_text: str | None = DEFAULT_CTA,
) -> Path:
    if not words:
        raise ValueError("no word timings — cannot assemble")
    total = words[-1].end
    durations = image_durations(beats, words, total=total)
    ass_path = out_dir / "captions.ass"
    ass_path.write_text(build_ass(
        words, title=title, title_end=durations[0] if title else None,
        cta_text=cta_text,
        cta_start=total if cta_text else None,
        cta_end=total + CTA_TOTAL_S if cta_text else None,
    ))
    out_path = out_dir / "video.mp4"
    cmd = build_ffmpeg_cmd(
        images, durations, audio_path, ass_path, out_path,
        music_path=music_path, motion_clips=motion_clips, cta_text=cta_text,
    )
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {proc.stderr[-2000:]}")
    return out_path
