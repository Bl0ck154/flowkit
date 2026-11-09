#!/usr/bin/env python3
"""
FlowKit — Multi-Chapter Cinematic Master Film Compiler
Assembles independent chapter videos into a seamless, Hollywood-grade Master Film.

Features:
1. Dynamic Interstitial Chapter Bumpers (obsidian canvas, antique gold typography, 40-60Hz sub-bass drone).
2. Micro Ken Burns zoom (1.0x -> 1.04x) on chapter cards.
3. Dip-to-black video & audio crossfades (0.8s standard).
4. Automated YouTube Chapter Timestamps generation for video descriptions.
5. Codec-safe normalization & concatenation.

Usage:
    python scripts/build_master_film.py --project-dir output/hong_nhat_thang_long --chapters 1 2 3 4 5
    python scripts/build_master_film.py --config config/master_film_config.json
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def run_command(cmd, desc=""):
    """Execute subprocess and return success status and output."""
    if desc:
        print(f"  [EXEC] {desc}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  [ERROR] {res.stderr.strip()}", file=sys.stderr)
        return False, res.stderr
    return True, res.stdout


def get_media_duration(file_path):
    """Retrieve media duration in seconds via ffprobe."""
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


def format_timestamp(seconds):
    """Convert seconds into MM:SS or HH:MM:SS format."""
    total_sec = int(round(seconds))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def create_bumper_card_pil(
    category_text,
    main_title,
    subtitle_text,
    output_path,
    width=1280,
    height=720,
    accent_color=(212, 175, 55),  # Antique Gold
    glow_color=(180, 50, 30)      # Crimson Ambience
):
    """Render a cinematic chapter interstitial title card using PIL."""
    img = Image.new('RGB', (width, height), color=(10, 8, 12))
    pixels = img.load()
    cx, cy = width / 2.0, height / 2.0
    max_dist = math.sqrt(cx**2 + cy**2)

    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2) / max_dist
            radial = max(0.0, 1.0 - dist * 1.3)
            r = int(10 + radial * glow_color[0] * 0.22)
            g = int(8 + radial * glow_color[1] * 0.12)
            b = int(12 + radial * glow_color[2] * 0.12)
            pixels[x, y] = (min(255, r), min(255, g), min(255, b))

    draw = ImageDraw.Draw(img)

    # Resolve fonts (with Windows fallback)
    font_cat_path = 'C:/Windows/Fonts/timesbd.ttf' if os.name == 'nt' else '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
    font_sub_path = 'C:/Windows/Fonts/arial.ttf' if os.name == 'nt' else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

    try:
        scale = height / 720.0
        font_cat = ImageFont.truetype(font_cat_path, int(26 * scale))
        font_title = ImageFont.truetype(font_cat_path, int(50 * scale))
        font_sub = ImageFont.truetype(font_sub_path, int(24 * scale))
        font_dec = ImageFont.truetype(font_cat_path, int(18 * scale))
    except Exception:
        font_cat = font_title = font_sub = font_dec = ImageFont.load_default()

    y_cat = int(height * 0.35)
    y_line1 = y_cat + int(35 * (height / 720.0))
    y_title = int(height * 0.50)
    y_line2 = y_title + int(45 * (height / 720.0))
    y_sub = int(height * 0.65)

    # Series Header
    draw.text((cx, y_cat), category_text, font=font_cat, fill=accent_color, anchor='mm')

    # Accent Dividers
    line_w = int(280 * (width / 1280.0))
    draw.line([(cx - line_w, y_line1), (cx + line_w, y_line1)], fill=(120, 95, 40), width=1)
    draw.text((cx, y_line1), "◆", font=font_dec, fill=accent_color, anchor='mm')

    # Main Chapter Title
    draw.text((cx, y_title), main_title, font=font_title, fill=(255, 255, 255), anchor='mm')

    draw.line([(cx - line_w, y_line2), (cx + line_w, y_line2)], fill=(120, 95, 40), width=1)
    draw.text((cx, y_line2), "◆", font=font_dec, fill=accent_color, anchor='mm')

    # Narrative Context / Subtitle
    if subtitle_text:
        draw.text((cx, y_sub), subtitle_text, font=font_sub, fill=(200, 205, 215), anchor='mm')

    # Letterbox border framing
    margin_x = int(60 * (width / 1280.0))
    margin_y = int(40 * (height / 720.0))
    draw.rectangle([margin_x, margin_y, width - margin_x, height - margin_y], outline=(45, 38, 25), width=1)
    draw.rectangle([margin_x + 4, margin_y + 4, width - margin_x - 4, height - margin_y - 4], outline=(25, 20, 15), width=1)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, quality=95)
    return True


def render_bumper_video(card_img_path, output_video_path, duration=3.5, width=1280, height=720, fps=24):
    """Render a dynamic bumper video with Ken Burns micro-zoom and sub-bass brown drone."""
    if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 10000:
        return True

    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
    num_frames = int(duration * fps)
    
    # 0.8s fade in, 1.0s fade out
    fade_out_start = max(0.5, duration - 1.0)
    filter_complex = (
        f"[0:v]zoompan=z='min(zoom+0.0006,1.05)':d={num_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps},"
        f"fade=t=in:st=0:d=0.8,fade=t=out:st={fade_out_start:.2f}:d=1.0[vout];"
        f"[1:a]lowpass=f=160,volume=3.2,afade=t=in:ss=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.0[aout]"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', str(card_img_path),
        '-f', 'lavfi', '-t', str(duration), '-i', f'anoisesrc=d={duration}:c=brown:r=48000:a=0.12',
        '-filter_complex', filter_complex,
        '-map', '[vout]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        '-t', str(duration),
        str(output_video_path)
    ]
    ok, _ = run_command(cmd, f"Rendering bumper video: {output_video_path}")
    return ok


def apply_fades_to_chapter(input_video_path, output_video_path, fade_dur=0.8):
    """Apply head/tail video and audio dips to black."""
    if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 10000:
        return True

    dur = get_media_duration(input_video_path)
    if dur <= 0:
        return False

    fade_out_st = max(0.0, dur - fade_dur)
    filter_complex = (
        f"[0:v]fade=t=in:st=0:d={fade_dur},fade=t=out:st={fade_out_st:.2f}:d={fade_dur}[vout];"
        f"[0:a]afade=t=in:ss=0:d={fade_dur},afade=t=out:st={fade_out_st:.2f}:d={fade_dur}[aout]"
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_video_path),
        '-filter_complex', filter_complex,
        '-map', '[vout]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        str(output_video_path)
    ]
    ok, _ = run_command(cmd, f"Fading chapter: {input_video_path} -> {output_video_path}")
    return ok


def build_master_film(
    project_dir,
    chapters,
    series_title="HỒNG NHẬT THĂNG LONG",
    chapter_metadata=None,
    output_master=None,
    width=1280,
    height=720,
    fps=24,
    bumper_dur=3.5,
    fade_dur=0.8,
    skip_bumpers=False
):
    """Main orchestration function for building a master film."""
    project_path = Path(project_dir)
    slug = project_path.name
    temp_dir = project_path / ".master_film_cache"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if not output_master:
        output_master = str(project_path / f"{slug}_CINEMATIC_MASTER.mp4")

    print(f"\n=======================================================")
    print(f"🎬 FLOWKIT CINEMATIC MASTER FILM COMPILER")
    print(f"Series: {series_title}")
    print(f"Project Directory: {project_dir}")
    print(f"Chapters Count: {len(chapters)}")
    print(f"Output Master: {output_master}")
    print(f"=======================================================\n")

    # Resolve chapter files
    chapter_entries = []
    for ch in chapters:
        # Check standard filename patterns
        candidates = [
            project_path / f"{slug}_ch{ch}_final.mp4",
            project_path / f"ch{ch}_final.mp4",
            project_path / f"chapter_{ch}.mp4",
            project_path / f"ch{ch}.mp4",
        ]
        found = None
        for cand in candidates:
            if cand.exists():
                found = cand
                break
        
        if not found:
            # Fallback search by pattern
            matches = list(project_path.glob(f"*ch{ch}*.mp4"))
            if matches:
                found = matches[0]

        if not found:
            print(f"❌ Error: Cannot find chapter video for chapter '{ch}' in {project_dir}", file=sys.stderr)
            return False

        meta = {}
        if chapter_metadata and str(ch) in chapter_metadata:
            meta = chapter_metadata[str(ch)]
        elif chapter_metadata and ch in chapter_metadata:
            meta = chapter_metadata[ch]

        title = meta.get("title", f"CHƯƠNG {ch}")
        subtitle = meta.get("subtitle", "")
        chapter_entries.append({
            "chapter": ch,
            "raw_video": found,
            "title": title,
            "subtitle": subtitle
        })

    playback_sequence = []
    current_timeline_sec = 0.0
    youtube_timestamps = []

    # 1. Bumpers and Transitions
    for idx, item in enumerate(chapter_entries, 1):
        ch = item["chapter"]
        raw_video = item["raw_video"]

        if not skip_bumpers:
            card_img = temp_dir / f"card_ch{ch}.png"
            bumper_mp4 = temp_dir / f"bumper_ch{ch}.mp4"

            if not card_img.exists():
                if HAS_PIL:
                    create_bumper_card_pil(
                        category_text=series_title,
                        main_title=item["title"],
                        subtitle_text=item["subtitle"],
                        output_path=str(card_img),
                        width=width,
                        height=height
                    )
            
            render_bumper_video(
                card_img_path=str(card_img),
                output_video_path=str(bumper_mp4),
                duration=bumper_dur,
                width=width,
                height=height,
                fps=fps
            )

            # Record timestamp for YouTube
            ts_str = format_timestamp(current_timeline_sec)
            youtube_timestamps.append(f"{ts_str} - {item['title']}: {item['subtitle']}" if item['subtitle'] else f"{ts_str} - {item['title']}")
            
            playback_sequence.append(str(bumper_mp4))
            current_timeline_sec += bumper_dur

        # Faded chapter
        faded_mp4 = temp_dir / f"ch{ch}_smooth.mp4"
        apply_fades_to_chapter(str(raw_video), str(faded_mp4), fade_dur=fade_dur)
        playback_sequence.append(str(faded_mp4))
        
        ch_dur = get_media_duration(str(raw_video))
        current_timeline_sec += ch_dur

    # Outro Bumper if provided
    outro_meta = chapter_metadata.get("outro") if chapter_metadata else None
    if outro_meta and not skip_bumpers:
        card_outro = temp_dir / "card_outro.png"
        bumper_outro = temp_dir / "bumper_outro.mp4"
        if HAS_PIL and not card_outro.exists():
            create_bumper_card_pil(
                category_text=series_title,
                main_title=outro_meta.get("title", "HẾT PHẦN 1"),
                subtitle_text=outro_meta.get("subtitle", "Đón xem Phần 2"),
                output_path=str(card_outro),
                width=width,
                height=height
            )
        render_bumper_video(str(card_outro), str(bumper_outro), duration=bumper_dur, width=width, height=height, fps=fps)
        ts_str = format_timestamp(current_timeline_sec)
        youtube_timestamps.append(f"{ts_str} - {outro_meta.get('title', 'KẾT THÚC')}")
        playback_sequence.append(str(bumper_outro))
        current_timeline_sec += bumper_dur

    # 2. Concat
    concat_txt = temp_dir / "master_concat_list.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in playback_sequence:
            abs_p = Path(p).resolve().as_posix()
            f.write(f"file '{abs_p}'\n")

    print(f"\n[STITCH] Concatenating {len(playback_sequence)} video blocks into final master...")
    cmd_concat = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_txt),
        '-c', 'copy',
        str(output_master)
    ]
    ok, _ = run_command(cmd_concat, "FFmpeg stream copy concat")
    if not ok:
        print("Falling back to re-encoding concat...", file=sys.stderr)
        cmd_concat_reencode = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_txt),
            '-c:v', 'libx264', '-crf', '18', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '192k',
            str(output_master)
        ]
        ok, _ = run_command(cmd_concat_reencode, "FFmpeg re-encode concat")
        if not ok:
            return False

    final_size_mb = os.path.getsize(output_master) / (1024 * 1024)
    final_dur = get_media_duration(output_master)

    # 3. Print Results & YouTube Chapters
    yt_file = project_path / f"{slug}_YOUTUBE_CHAPTERS.txt"
    with open(yt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(youtube_timestamps))

    print(f"\n=======================================================")
    print(f"✅ CINEMATIC MASTER FILM GENERATED SUCCESSFULLY!")
    print(f"Output File:     {output_master}")
    print(f"Total Size:      {final_size_mb:.2f} MB")
    print(f"Total Duration:  {final_dur:.1f}s ({final_dur/60:.2f} minutes)")
    print(f"YouTube Chapters File: {yt_file}")
    print(f"-------------------------------------------------------")
    print("📋 YouTube Chapter Timestamps for Description:")
    for line in youtube_timestamps:
        print(f"  {line}")
    print(f"=======================================================\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="FlowKit Multi-Chapter Master Film Compiler")
    parser.add_argument("--project-dir", required=True, help="Directory containing chapter video files")
    parser.add_argument("--chapters", nargs="+", default=["1", "2", "3", "4", "5"], help="List of chapter identifiers")
    parser.add_argument("--title", default="HỒNG NHẬT THĂNG LONG", help="Series or movie main title")
    parser.add_argument("--config", help="Optional JSON config file with chapter titles and subtitles")
    parser.add_argument("--output", help="Output path for the master film MP4")
    parser.add_argument("--resolution", default="1280x720", help="Resolution WxH (e.g. 1280x720 or 1920x1080)")
    parser.add_argument("--fps", type=int, default=24, help="Target frames per second")
    parser.add_argument("--bumper-duration", type=float, default=3.5, help="Duration of chapter interstitial card (sec)")
    parser.add_argument("--fade-duration", type=float, default=0.8, help="Fade duration for crossfades/dips (sec)")
    parser.add_argument("--no-bumpers", action="store_true", help="Skip bumper title cards")

    args = parser.parse_args()

    width, height = [int(x) for x in args.resolution.split("x")]
    
    chapter_meta = {}
    if args.config and os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8") as f:
            chapter_meta = json.load(f)

    # Built-in default metadata for Hong Nhat Thang Long if not provided
    if not chapter_meta and "hong_nhat" in args.project_dir.lower():
        chapter_meta = {
            "1": {"title": "CHƯƠNG I: NGÀY TRỞ VỀ", "subtitle": "Tầng hầm B3 Mễ Trì — Khởi đầu chuỗi ngày sinh tồn"},
            "2": {"title": "CHƯƠNG II: NGÀY NGỌC TRẦM", "subtitle": "Bốn mươi bốn ngày trước thảm họa — Bão nhiệt 65°C tấn công"},
            "3": {"title": "CHƯƠNG III: LA PHÙ KHÔNG CÒN LỬA", "subtitle": "Ba mươi ngày trước thảm họa — Bí mật chuỗi cung ứng ngầm"},
            "4": {"title": "CHƯƠNG IV: HỒNG NHẬT GIỮA ĐÊM ĐEN", "subtitle": "Mười lăm ngày trước thảm họa — Trận chiến cống ngầm Đại Hà"},
            "5": {"title": "CHƯƠNG V: THĂNG LONG PHÒNG TUYẾN", "subtitle": "Bảy ngày trước thảm họa — Lời thề giữ đất Thăng Long"},
            "outro": {"title": "HẾT PHẦN 1 — CHUỖI 5 CHƯƠNG ĐẦU", "subtitle": "Đón xem Phần 2: Ngày Tận Thế Thăng Long"}
        }

    ok = build_master_film(
        project_dir=args.project_dir,
        chapters=args.chapters,
        series_title=args.title,
        chapter_metadata=chapter_meta,
        output_master=args.output,
        width=width,
        height=height,
        fps=args.fps,
        bumper_dur=args.bumper_duration,
        fade_dur=args.fade_duration,
        skip_bumpers=args.no_bumpers
    )

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
