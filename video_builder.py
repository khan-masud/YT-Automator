"""
Video Builder Module.

Assembles final video files using FFmpeg and FFprobe subprocess calls.
Generates SRT captions and handles video/image segment composition.
"""
import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple


def _ensure_ffmpeg_in_path() -> None:
    """Ensures FFmpeg and FFprobe binaries are accessible in OS environment PATH."""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    local_appdata = os.getenv("LOCALAPPDATA", "")
    if local_appdata:
        winget_pkgs = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for p in winget_pkgs.glob("Gyan.FFmpeg*/**/bin"):
                if (p / "ffmpeg.exe").exists():
                    os.environ["PATH"] += os.pathsep + str(p)
                    return


_ensure_ffmpeg_in_path()


def _run(cmd: List[str], cwd: str = None) -> subprocess.CompletedProcess:
    """Runs a subprocess command and raises RuntimeError on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg command execution failed:\n{' '.join(cmd)}\n\nSTDERR:\n{result.stderr[-2000:]}")
    return result


def get_audio_duration(path: str) -> float:
    """Returns the duration of an audio file in seconds via FFprobe."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed to inspect audio file: {path}\nSTDERR: {result.stderr}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def build_srt(word_boundaries: List[Dict[str, Any]], out_path: Path, words_per_caption: int = 3) -> None:
    """Builds an SRT subtitle file from word-level timing boundaries."""
    def fmt(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: List[str] = []
    idx = 1
    for i in range(0, len(word_boundaries), words_per_caption):
        chunk = word_boundaries[i:i + words_per_caption]
        if not chunk:
            continue
        start = chunk[0]["start"]
        end = chunk[-1]["start"] + chunk[-1]["duration"]
        text = " ".join(w["text"] for w in chunk)
        lines.append(f"{idx}\n{fmt(start)} --> {fmt(end)}\n{text}\n")
        idx += 1

    if not lines:
        lines.append("1\n00:00:00,000 --> 00:00:05,000\n \n")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def _build_segment(clip: Dict[str, Any], duration: float, size: Tuple[int, int], out_path: Path) -> None:
    """Converts a single media clip or image into a standard MP4 video segment."""
    w, h = size
    if clip["type"] == "video" and clip["path"]:
        cmd = [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", clip["path"],
            "-t", str(duration),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30",
            "-an", str(out_path),
        ]
    elif clip["type"] == "image" and clip["path"]:
        zoom_frames = int(duration * 30)
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", clip["path"],
            "-t", str(duration),
            "-vf",
            f"scale={w*2}:{h*2},zoompan=z='min(zoom+0.0015,1.3)':d={zoom_frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=30",
            "-an", str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x1a1a2e:s={w}x{h}:d={duration}:r=30",
            str(out_path),
        ]
    _run(cmd)


def build_video(clips: List[Dict[str, Any]], segment_duration: float, size: Tuple[int, int],
                audio_path: str, srt_path: Path, out_path: Path, work_dir: Path) -> Path:
    """
    Assembles video clips, voiceover audio, and burnt-in subtitles into the final MP4 video file.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    segment_paths: List[Path] = []
    for i, clip in enumerate(clips):
        seg_path = work_dir / f"seg_{i:02d}.mp4"
        _build_segment(clip, segment_duration, size, seg_path)
        segment_paths.append(seg_path)

    concat_list = work_dir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{p.resolve()}'" for p in segment_paths), encoding="utf-8")

    silent_video = work_dir / "silent_concat.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(silent_video),
    ])

    # Modern YouTube Shorts / Reels subtitle style: Centered near the lower bottom area
    w, h = size
    font_size = 55 if h > w else 45
    margin_v = 280 if h > w else 90
    subtitle_style = (
        f"PlayResX={w},PlayResY={h},FontName=Arial,FontSize={font_size},Bold=1,"
        f"PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=4,Shadow=1,Alignment=2,MarginV={margin_v}"
    )
    _run([
        "ffmpeg", "-y", "-i", str(silent_video.resolve()), "-i", str(Path(audio_path).resolve()),
        "-vf", f"subtitles='{srt_path.name}':force_style='{subtitle_style}'",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path.resolve()),
    ], cwd=str(srt_path.parent))
    return out_path
