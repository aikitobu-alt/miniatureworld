"""ffmpeg-based video assembly: concat scene clips, burn captions, mix audio."""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

from .config import load_config, project_root
from .models import RenderedScene, Script


def _ass_header(play_res_x: int, play_res_y: int, font_size: int, outline: int) -> str:
    return (
        "[Script Info]\n"
        f"PlayResX: {play_res_x}\nPlayResY: {play_res_y}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,Inter,{font_size},&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,0,1,{outline},0,2,60,60,260,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _fmt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _write_ass(scenes: list[RenderedScene], path: Path) -> Path:
    cfg = load_config().short
    body = _ass_header(cfg.resolution[0], cfg.resolution[1], cfg.subtitle_font_size, cfg.subtitle_outline)
    t = 0.0
    for rs in scenes:
        start = t
        end = t + rs.scene.duration_seconds
        text = rs.scene.caption.replace("\n", "\\N")
        body += f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Caption,,0,0,0,,{text}\n"
        t = end
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _pick_music() -> Path | None:
    d = project_root() / "assets" / "music"
    if not d.exists():
        return None
    loops = [p for p in d.iterdir() if p.suffix.lower() in {".mp3", ".wav", ".m4a"}]
    if not loops:
        return None
    return random.choice(loops)


def assemble(
    script: Script,
    scenes: list[RenderedScene],
    voiceover_path: Path | None,
    out_path: Path,
) -> Path:
    cfg = load_config()
    w, h = cfg.short.resolution
    fps = cfg.short.fps
    workdir = out_path.parent
    workdir.mkdir(parents=True, exist_ok=True)

    # 1) Normalize each clip to 1080x1920 @ fps, no audio
    normed: list[Path] = []
    for rs in scenes:
        n = workdir / f"norm_{rs.scene.index:02d}.mp4"
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps={fps},setsar=1"
        )
        cmd = [
            "ffmpeg", "-y", "-i", str(rs.video_path),
            "-vf", vf,
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-t", f"{rs.scene.duration_seconds}",
            str(n),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        normed.append(n)

    # 2) Concat via concat demuxer
    concat_list = workdir / "concat.txt"
    concat_list.write_text("".join(f"file '{p}'\n" for p in normed), encoding="utf-8")
    concatted = workdir / "concat.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(concatted)],
        check=True, capture_output=True,
    )

    # 3) Burn captions
    ass_path = _write_ass(scenes, workdir / "captions.ass")
    captioned = workdir / "captioned.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(concatted),
         "-vf", f"ass={ass_path}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "copy",
         str(captioned)],
        check=True, capture_output=True,
    )

    # 4) Mix audio: optional voiceover + optional music bed
    music = _pick_music()
    ducked = None
    audio_inputs: list[str] = []
    filters: list[str] = []
    if voiceover_path:
        audio_inputs.extend(["-i", str(voiceover_path)])
    if music:
        audio_inputs.extend(["-stream_loop", "-1", "-i", str(music)])

    if voiceover_path and music:
        vo_idx = 1
        music_idx = 2
        filters.append(
            f"[{vo_idx}:a]volume={cfg.music.voiceover_volume_db}dB[vo];"
            f"[{music_idx}:a]volume={cfg.music.bed_volume_db}dB,aloop=loop=-1:size=2e+09[bed];"
            f"[vo][bed]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        amap = "[aout]"
    elif voiceover_path:
        filters.append(f"[1:a]volume={cfg.music.voiceover_volume_db}dB[aout]")
        amap = "[aout]"
    elif music:
        filters.append(
            f"[1:a]volume={cfg.music.bed_volume_db}dB,aloop=loop=-1:size=2e+09[aout]"
        )
        amap = "[aout]"
    else:
        amap = None

    cmd = ["ffmpeg", "-y", "-i", str(captioned)] + audio_inputs
    if amap:
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", "0:v", "-map", amap,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
        ]
    else:
        cmd += ["-c:v", "copy", "-an"]
    cmd += [str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
