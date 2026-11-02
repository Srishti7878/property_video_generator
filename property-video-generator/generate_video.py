"""
Assemble a short promotional property video using ffmpeg.
Fully Windows-compatible: text overlays are burned with Pillow (no drawtext).
"""

import os
import platform
import subprocess
import tempfile
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont


def _create_ambient_audio(duration: float = 30.0) -> str:
    """
    Create a very soft ambient background tone using ffmpeg.
    Returns path to a temporary aac/mp3 file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".aac", delete=False)
    tmp.close()
    # Soft low sine wave + light noise, very low volume
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=220:duration={duration}",
        "-f", "lavfi",
        "-i", f"anoisesrc=d={duration}:c=pink:a=0.02",
        "-filter_complex",
        "[0:a]volume=0.04[a0];[1:a]volume=0.03[a1];[a0][a1]amix=inputs=2:duration=first[a]",
        "-map", "[a]",
        "-c:a", "aac", "-b:a", "64k",
        tmp.name
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: just a quiet sine
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency=180:duration={duration}",
            "-af", "volume=0.05",
            "-c:a", "aac", "-b:a", "64k",
            tmp.name
        ]
        subprocess.run(cmd, capture_output=True)
    return tmp.name


def _get_font(font_size: int = 48):
    """Return a usable font."""
    candidates = []
    if platform.system() == "Windows":
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    return ImageFont.load_default()


def _create_text_card(
    text: str,
    width: int = 1920,
    height: int = 1080,
    bg_color: tuple = (15, 23, 42),
    text_color: tuple = (255, 255, 255),
    font_size: int = 48,
    accent: bool = False,
) -> str:
    """Create a polished centered text card."""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)
    small_font = _get_font(22)

    # Subtle top accent bar
    draw.rectangle([0, 0, width, 8], fill=(56, 189, 248))

    # Bottom accent bar
    draw.rectangle([0, height - 8, width, height], fill=(56, 189, 248))

    words = text.split()
    lines = []
    current = ""
    max_width = width - 160
    for w in words:
        test = f"{current} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    total_h = len(lines) * (font_size + 16)
    y = (height - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw.text((x, y), line, fill=text_color, font=font)
        y += font_size + 16

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


def _prepare_image_with_caption(
    image_path: str,
    caption: str = "",
    price: str = "",
    width: int = 1920,
    height: int = 1080,
) -> str:
    """
    Resize image to 1280x720, add optional price badge and caption bar.
    """
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((width, height), Image.Resampling.LANCZOS)

    background = Image.new("RGB", (width, height), (0, 0, 0))
    offset = ((width - img.width) // 2, (height - img.height) // 2)
    background.paste(img, offset)
    draw = ImageDraw.Draw(background)

    # Price badge (top-right)
    if price:
        badge_font = _get_font(28)
        badge_text = price
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 18, 10
        bx1 = width - tw - pad_x * 2 - 30
        by1 = 25
        bx2 = width - 30
        by2 = by1 + th + pad_y * 2
        # Rounded-ish rectangle
        draw.rounded_rectangle([bx1, by1, bx2, by2], radius=8, fill=(15, 23, 42))
        draw.rounded_rectangle([bx1, by1, bx2, by2], radius=8, outline=(56, 189, 248), width=2)
        draw.text((bx1 + pad_x, by1 + pad_y - 2), badge_text, fill=(255, 255, 255), font=badge_font)

    # Caption bar at bottom
    if caption:
        font = _get_font(32)
        words = caption.split()
        lines = []
        current = ""
        max_w = width - 100
        for w in words:
            test = f"{current} {w}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)

        line_h = 38
        bar_h = 18 + len(lines) * line_h
        bar_y = height - bar_h - 18

        overlay = Image.new("RGBA", (width, bar_h), (15, 23, 42, 200))
        background.paste(overlay, (0, bar_y), overlay)

        # Accent line above caption
        draw.rectangle([0, bar_y, width, bar_y + 3], fill=(56, 189, 248))

        y = bar_y + 12
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2
            draw.text((x, y), line, fill=(255, 255, 255), font=font)
            y += line_h

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    background.save(tmp.name)
    return tmp.name


def generate_video(
    property_data: Dict,
    script: Dict,
    image_paths: List[str],
    output_path: str = "output/property_video.mp4",
    duration_per_image: float = 4.0,
    background_music: str = None,
    voiceover_path: str = None,
) -> str:
    """
    Build the final MP4 video.
    Text overlays are burned with Pillow (reliable on Windows).
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    valid_images = []
    for p in image_paths:
        if os.path.isfile(p):
            valid_images.append(p)
        else:
            print(f"Warning: image not found → {p}")

    if not valid_images:
        raise ValueError(
            "No valid images provided. Please supply at least one existing image path.\n"
            "Example: sample_data/img1.jpg"
        )

    valid_images = valid_images[:8]
    temp_files = []

    try:
        # Title + Opening cards
        title_img = _create_text_card(script["title"], font_size=54)
        temp_files.append(title_img)

        opening_img = _create_text_card(script["opening"], font_size=34)
        temp_files.append(opening_img)

        # Property images with captions + price badge
        price = str(property_data.get("price", "")).strip()
        scene_images = []
        for i, img_path in enumerate(valid_images):
            caption = ""
            if i < len(script["scenes"]):
                caption = script["scenes"][i]["caption"]
            prepared = _prepare_image_with_caption(img_path, caption=caption, price=price)
            temp_files.append(prepared)
            scene_images.append(prepared)

        # CTA card
        cta_img = _create_text_card(script["cta"], font_size=40)
        temp_files.append(cta_img)

        clips = []

        def make_clip(image_path: str, duration: float) -> str:
            clip_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
            temp_files.append(clip_path)

            vf = f"fade=t=in:st=0:d=0.4,fade=t=out:st={duration-0.4}:d=0.4"

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-c:v", "libx264", "-t", str(duration),
                "-pix_fmt", "yuv420p", "-r", "25",
                "-vf", vf,
                clip_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("\n--- ffmpeg error ---")
                print(result.stderr[-700:] if result.stderr else "No stderr")
                print("--------------------\n")
                raise RuntimeError(
                    f"ffmpeg failed (exit code {result.returncode}).\n"
                    "Make sure ffmpeg is installed and in your PATH."
                )
            return clip_path

        # Build clips
        clips.append(make_clip(title_img, 3.0))
        clips.append(make_clip(opening_img, 3.0))

        for img in scene_images:
            clips.append(make_clip(img, duration_per_image))

        clips.append(make_clip(cta_img, 4.0))

        # Concatenate
        list_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        for c in clips:
            # Forward slashes work better with ffmpeg on Windows
            safe_path = c.replace("\\", "/")
            list_file.write(f"file '{safe_path}'\n")
        list_file.close()
        temp_files.append(list_file.name)

        final_tmp = output_path + ".tmp.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file.name,
            "-c", "copy",
            final_tmp
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr[-600:] if result.stderr else "")
            raise RuntimeError("ffmpeg concat failed")

        # Add voice-over and/or background music
        has_voice = voiceover_path and os.path.isfile(voiceover_path)
        has_music = background_music and os.path.isfile(background_music)

        # If no custom music provided, generate a soft ambient tone
        ambient_path = None
        if not has_music and has_voice:
            try:
                print("Creating soft ambient background...")
                ambient_path = _create_ambient_audio(duration=35.0)
                temp_files.append(ambient_path)
                has_music = True
                background_music = ambient_path
            except Exception as e:
                print(f"Could not create ambient audio: {e}")

        if has_voice or has_music:
            final_audio = output_path + ".audio.mp4"

            if has_voice and has_music:
                print("Adding voice-over + background music...")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", final_tmp,
                    "-i", voiceover_path,
                    "-stream_loop", "-1",
                    "-i", background_music,
                    "-filter_complex",
                    "[1:a]volume=1.0[voice];"
                    "[2:a]volume=0.12,afade=t=in:st=0:d=1.5[music];"
                    "[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    final_audio
                ]
            elif has_voice:
                print("Adding voice-over narration...")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", final_tmp,
                    "-i", voiceover_path,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-map", "0:v", "-map", "1:a",
                    "-shortest",
                    final_audio
                ]
            else:  # music only
                print(f"Adding background music...")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", final_tmp,
                    "-stream_loop", "-1",
                    "-i", background_music,
                    "-filter_complex",
                    "[1:a]volume=0.18,afade=t=in:st=0:d=1.5[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    final_audio
                ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                os.replace(final_audio, output_path)
                try:
                    os.remove(final_tmp)
                except Exception:
                    pass
            else:
                print("Warning: could not add audio, saving silent video.")
                print(result.stderr[-400:] if result.stderr else "")
                os.replace(final_tmp, output_path)
        else:
            os.replace(final_tmp, output_path)

        print(f"\nVideo successfully saved to: {output_path}")
        return output_path

    finally:
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
