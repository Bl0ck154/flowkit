#!/usr/bin/env python3
"""
FlowKit — Subtitle (.srt / .vtt) Generator & Hardsub Burner
Extracts narrator text and timing from scenes or local project files to generate:
1. SubRip (.srt) subtitle files (for YouTube captions and VLC)
2. WebVTT (.vtt) subtitle files (for web players)
3. Hardsub Burning: Directly burns stylized, cinematic subtitles into video frames via FFmpeg.

Styles:
- cinematic_gold: Antique gold text (&H0080C2E6), dark outline, elegant margins
- clean_white: Crisp white text (&H00FFFFFF), 1.8px dark outline, subtle shadow
- cyber_amber: Glowing amber text (&H0000D7FF), high-contrast outline
- emerald_hud: Military sci-fi HUD light-green (&H00C0FFC0)

Usage:
    python scripts/generate_subtitles.py --video-id <VID> --output output/<slug>/subtitles.srt
    python scripts/generate_subtitles.py --project-dir output/hong_nhat_thang_long --burn-subtitles --input-video output/hong_nhat_thang_long/hong_nhat_thang_long_CINEMATIC_MASTER.mp4
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


SUBTITLE_STYLES = {
    "cinematic_gold": "FontName=Arial,FontSize=20,PrimaryColour=&H0080C2E6,OutlineColour=&H0008080A,BorderStyle=1,Outline=2.0,Shadow=1.5,MarginV=35",
    "clean_white": "FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1.8,Shadow=1.0,MarginV=30",
    "cyber_amber": "FontName=Arial,FontSize=20,PrimaryColour=&H0000D7FF,OutlineColour=&H00000020,BorderStyle=1,Outline=2.2,Shadow=1.5,MarginV=35",
    "emerald_hud": "FontName=Arial,FontSize=20,PrimaryColour=&H00C0FFC0,OutlineColour=&H00002000,BorderStyle=1,Outline=2.0,Shadow=1.5,MarginV=35",
}


def format_srt_time(seconds):
    """Format seconds into SRT timestamp: HH:MM:SS,mmm"""
    millis = int(round((seconds - int(seconds)) * 1000))
    total_sec = int(seconds)
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds):
    """Format seconds into WebVTT timestamp: HH:MM:SS.mmm"""
    millis = int(round((seconds - int(seconds)) * 1000))
    total_sec = int(seconds)
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def wrap_subtitle_text(text, max_chars=42):
    """Split long subtitle text into max 2 readable lines."""
    words = text.strip().split()
    if not words:
        return ""
    
    lines = []
    cur_line = []
    cur_len = 0

    for w in words:
        if cur_len + len(w) + (1 if cur_line else 0) > max_chars and cur_line:
            lines.append(" ".join(cur_line))
            cur_line = [w]
            cur_len = len(w)
        else:
            cur_line.append(w)
            cur_len += len(w) + (1 if cur_len > 0 else 0)

    if cur_line:
        lines.append(" ".join(cur_line))

    # Return at most 2 lines per subtitle card, joined by newline
    return "\n".join(lines[:2])


def get_audio_duration(file_path):
    """Get audio duration in seconds using ffprobe."""
    if not os.path.exists(file_path):
        return 0.0
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def fetch_scenes_api(video_id, base_url="http://127.0.0.1:8100"):
    """Fetch scenes for a given video_id from FlowKit API."""
    url = f"{base_url}/api/scenes?video_id={video_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "FlowKit-Subtitle"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return sorted(data, key=lambda s: s.get("display_order", 0))
    except Exception as e:
        print(f"Error fetching scenes from API: {e}", file=sys.stderr)
        return []


def generate_subtitles_from_scenes(scenes, output_base, buffer_sec=0.5, default_scene_dur=8.0):
    """Generate .srt and .vtt files given scene metadata list."""
    srt_entries = []
    vtt_entries = ["WEBVTT\n"]
    
    current_time = 0.0
    sub_index = 1

    for sc in scenes:
        narrator = sc.get("narrator_text", "").strip()
        dur = sc.get("duration") or default_scene_dur
        
        # If there's narrator text
        if narrator:
            start_t = current_time
            end_t = current_time + max(2.0, dur - buffer_sec)
            
            wrapped = wrap_subtitle_text(narrator)
            
            srt_entries.append(
                f"{sub_index}\n"
                f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}\n"
                f"{wrapped}\n"
            )
            
            vtt_entries.append(
                f"{sub_index}\n"
                f"{format_vtt_time(start_t)} --> {format_vtt_time(end_t)}\n"
                f"{wrapped}\n"
            )
            sub_index += 1

        current_time += dur

    srt_path = output_base.with_suffix(".srt")
    vtt_path = output_base.with_suffix(".vtt")

    srt_path.write_text("\n".join(srt_entries), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_entries), encoding="utf-8")

    print(f"✅ Generated SRT subtitles: {srt_path} ({sub_index - 1} entries)")
    print(f"✅ Generated VTT subtitles: {vtt_path}")
    return srt_path, vtt_path


def burn_subtitles_to_video(input_video_path, srt_path, output_video_path=None, style="cinematic_gold"):
    """Burn subtitles directly into video frames using FFmpeg libass subtitles filter."""
    in_p = Path(input_video_path)
    if not in_p.exists():
        print(f"❌ Input video not found: {input_video_path}", file=sys.stderr)
        return False

    if not output_video_path:
        output_video_path = in_p.parent / f"{in_p.stem}_hardsub.mp4"
    else:
        output_video_path = Path(output_video_path)

    style_str = SUBTITLE_STYLES.get(style, SUBTITLE_STYLES["cinematic_gold"])
    
    # Format srt path for FFmpeg filter:
    # Use forward slashes and escape colon for Windows drives (e.g. D\:/path)
    clean_srt = str(Path(srt_path).resolve()).replace('\\', '/')
    clean_srt = clean_srt.replace(':', '\\:')
    
    vf = f"subtitles='{clean_srt}':force_style='{style_str}'"

    print(f"\n🎬 Burning subtitles into video: {input_video_path}")
    print(f"  Style: {style}")
    print(f"  Output: {output_video_path}")

    cmd = [
        'ffmpeg', '-y',
        '-i', str(in_p),
        '-vf', vf,
        '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
        '-c:a', 'copy',
        str(output_video_path)
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Error burning subtitles: {res.stderr.strip()}", file=sys.stderr)
        return False

    size_mb = os.path.getsize(output_video_path) / (1024 * 1024)
    print(f"✅ Subtitles burned successfully: {output_video_path} ({size_mb:.2f} MB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="FlowKit Subtitle (.srt / .vtt) Generator & Hardsub Burner")
    parser.add_argument("--video-id", help="FlowKit Video ID to fetch scenes via API")
    parser.add_argument("--project-dir", help="Project output directory containing project metadata or scenes")
    parser.add_argument("--output", help="Output path (without extension or .srt)")
    parser.add_argument("--buffer", type=float, default=0.5, help="Audio tail buffer in seconds")
    parser.add_argument("--api-url", default="http://127.0.0.1:8100", help="FlowKit base URL")
    parser.add_argument("--burn-subtitles", "--burn", action="store_true", help="Burn subtitles directly into video")
    parser.add_argument("--input-video", help="Input video file to burn subtitles into")
    parser.add_argument("--output-video", help="Output path for video with burned subtitles")
    parser.add_argument("--style", choices=list(SUBTITLE_STYLES.keys()), default="cinematic_gold", help="Visual subtitle style")
    
    args = parser.parse_args()

    if not args.video_id and not args.project_dir and not args.input_video:
        print("Error: Either --video-id, --project-dir, or --input-video must be specified.", file=sys.stderr)
        sys.exit(1)

    scenes = []
    output_base = None

    if args.video_id:
        scenes = fetch_scenes_api(args.video_id, base_url=args.api_url)
        if not scenes:
            print(f"No scenes found for video_id {args.video_id}", file=sys.stderr)
            sys.exit(1)
        if args.output:
            output_base = Path(args.output)
        else:
            output_base = Path(f"output/subtitles_{args.video_id[:8]}")

    elif args.project_dir:
        proj_dir = Path(args.project_dir)
        scenes_json = proj_dir / "scenes.json"
        if not scenes_json.exists():
            scenes_json = proj_dir / "meta.json"
        
        if scenes_json.exists():
            with open(scenes_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                scenes = data if isinstance(data, list) else data.get("scenes", [])
        
        if not scenes:
            print(f"Could not load scenes from {proj_dir}", file=sys.stderr)
            sys.exit(1)

        output_base = Path(args.output) if args.output else proj_dir / f"{proj_dir.name}_subtitles"

    srt_path = None
    if scenes and output_base:
        output_base.parent.mkdir(parents=True, exist_ok=True)
        srt_path, _ = generate_subtitles_from_scenes(scenes, output_base, buffer_sec=args.buffer)
    elif args.output and Path(args.output).exists() and Path(args.output).suffix == ".srt":
        srt_path = Path(args.output)

    # If burn requested
    if args.burn_subtitles:
        in_vid = args.input_video
        if not in_vid and args.project_dir:
            proj_p = Path(args.project_dir)
            # Find candidate master video
            candidates = list(proj_p.glob("*CINEMATIC_MASTER.mp4")) + list(proj_p.glob("*final.mp4"))
            if candidates:
                in_vid = str(candidates[0])
        
        if not in_vid:
            print("Error: --burn-subtitles requires --input-video or an existing master video in --project-dir", file=sys.stderr)
            sys.exit(1)

        if not srt_path:
            print("Error: No SRT subtitle file found to burn.", file=sys.stderr)
            sys.exit(1)

        ok = burn_subtitles_to_video(in_vid, srt_path, output_video_path=args.output_video, style=args.style)
        if not ok:
            sys.exit(1)


if __name__ == '__main__':
    main()
