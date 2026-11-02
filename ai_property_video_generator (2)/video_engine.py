"""
video_engine.py - renders the property video (MoviePy 2.x + Pillow).

Per scene: real photo (cover-fit, or blurred-fill when the aspect ratio is far
from 16:9), slow Ken-Burns zoom, readable caption banner that fades in,
cross-dissolve between scenes, narration synced to the scene, soft music bed.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Callable, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from script_generator import UserInputError, VideoScript
from tts_engine import audio_duration, ffmpeg_exe, synthesize

W, H, FPS = 1280, 720, 30
XFADE = 0.7          # cross-dissolve seconds
VO_DELAY = 0.45      # narration starts this long after the scene starts
MAX_IMAGES = 8
MIN_DUR = {"intro": 5.0, "feature": 3.8, "outro": 5.0}
Log = Callable[[str], None]


# ---------------------------------------------------------------- images
def load_images(paths: List[str], log: Log = print) -> List[str]:
    """Keep only readable images; explain what was skipped."""
    ok = []
    for p in paths:
        if not p or not os.path.isfile(p):
            log(f"⚠ Image not found, skipped: {p}")
            continue
        try:
            with Image.open(p) as im:
                im.verify()
            ok.append(p)
        except Exception:
            log(f"⚠ Not a valid image, skipped: {os.path.basename(p)}")
    if not ok:
        raise UserInputError("No usable images. Provide at least one valid JPG/PNG property photo.")
    if len(ok) > MAX_IMAGES:
        log(f"⚠ {len(ok)} images given; using the first {MAX_IMAGES}.")
        ok = ok[:MAX_IMAGES]
    if len(ok) < 4:
        log(f"⚠ Only {len(ok)} image(s) - 4 to 8 give the best result; photos will be reused as needed.")
    return ok


def assign_images(n_scenes: int, images: List[str]) -> List[str]:
    """intro -> first image, outro -> last image, features -> the ones in between (in order)."""
    if n_scenes == 1:
        return [images[0]]
    mid = images[1:-1] if len(images) >= 3 else list(images)
    outro = images[-1] if len(images) >= 3 else images[0]
    feats = [mid[i % len(mid)] for i in range(n_scenes - 2)]
    return [images[0]] + feats + [outro]


def _font(size: int, bold=True):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _canvas(path: str, scale: float = 1.10) -> Image.Image:
    """Photo prepared on an oversized canvas (room for the zoom)."""
    cw, ch = int(W * scale), int(H * scale)
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    iw, ih = img.size
    ratio, target = iw / ih, cw / ch
    if abs(ratio - target) / target <= 0.12:                      # close to 16:9 -> fill
        s = max(cw / iw, ch / ih)
        r = img.resize((int(iw * s) + 1, int(ih * s) + 1), Image.LANCZOS)
        l, t = (r.width - cw) // 2, (r.height - ch) // 2
        out = r.crop((l, t, l + cw, t + ch))
    else:                                                          # portrait / 4:3 -> whole photo over blurred fill
        s = max(cw / iw, ch / ih)
        bg = img.resize((int(iw * s) + 1, int(ih * s) + 1), Image.BILINEAR)
        l, t = (bg.width - cw) // 2, (bg.height - ch) // 2
        bg = bg.crop((l, t, l + cw, t + ch)).filter(ImageFilter.GaussianBlur(28))
        bg = ImageEnhance.Brightness(bg).enhance(0.55)
        s2 = min(cw / iw, ch / ih)
        fg = img.resize((int(iw * s2), int(ih * s2)), Image.LANCZOS)
        fg = fg.filter(ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=2)) if s2 > 1.3 else fg
        bg.paste(fg, ((cw - fg.width) // 2, (ch - fg.height) // 2))
        out = bg
    return out


def _wrap(text: str, font, max_w: int) -> List[str]:
    lines: List[str] = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = f"{cur} {w}".strip()
            if font.getlength(t) <= max_w:
                cur = t
            else:
                lines.append(cur); cur = w
        lines.append(cur)
    return [l for l in lines if l]


GOLD, WHITE = (255, 214, 102), (255, 255, 255)


def _overlay(caption: str, scene_type: str, idx: int, total: int) -> Tuple[np.ndarray, np.ndarray]:
    """Return (rgb float32 HxWx3, alpha float32 HxWx1) of the caption layer."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lines = caption.split("\n")

    def centered(y, text, font, fill):
        x = (W - font.getlength(text)) // 2
        d.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 190))
        d.text((x, y), text, font=font, fill=fill)

    if scene_type == "intro":
        f_big, f_mid = _font(66), _font(32, False)
        wrapped = _wrap(lines[0], f_big, W - 120)
        h = len(wrapped) * 78 + (len(lines) - 1) * 48 + 70
        top = H - h - 30
        d.rectangle([0, top, W, top + h], fill=(0, 0, 0, 165))
        d.rectangle([W // 2 - 60, top + 18, W // 2 + 60, top + 22], fill=GOLD + (255,))
        y = top + 36
        for l in wrapped:
            centered(y, l, f_big, WHITE); y += 78
        for k, l in enumerate(lines[1:]):
            centered(y, l, f_mid, GOLD if k == len(lines) - 2 and len(lines) > 2 else WHITE); y += 48
    else:
        big = scene_type == "outro"
        f = _font(40 if big else 36)
        f2 = _font(30, False)
        wrapped = _wrap(lines[0], f, W - 140)
        extra = lines[1:]
        h = len(wrapped) * 50 + len(extra) * 42 + 44
        top = H - h - 28
        d.rectangle([0, top, W, H], fill=(0, 0, 0, 175))
        d.rectangle([0, top, W, top + 4], fill=GOLD + (255,))
        y = top + 22
        for l in wrapped:
            centered(y, l, f, GOLD if big else WHITE); y += 50
        for l in extra:
            centered(y, l, f2, WHITE); y += 42
        if not big:   # small progress dots
            for i in range(total):
                cx = W // 2 - (total - 1) * 11 + i * 22
                d.ellipse([cx - 5, 26 - 5, cx + 5, 26 + 5], fill=(255, 255, 255, 230 if i == idx else 90))
    arr = np.asarray(layer, dtype=np.float32)
    return arr[..., :3], arr[..., 3:] / 255.0


class _Scene:
    """One scene: prepared canvas + caption layer; render(t) -> HxWx3 uint8 frame."""

    def __init__(self, photo, caption, scene_type, dur, idx, total):
        self.canvas = _canvas(photo)
        self.rgb, self.alpha = _overlay(caption, scene_type, idx, total)
        self.dur, self.zoom_in = dur, idx % 2 == 0

    def render(self, t):
        cw, ch = self.canvas.size
        p = min(1.0, max(0.0, t / self.dur))
        p = p if self.zoom_in else 1 - p
        p = p * p * (3 - 2 * p)                                   # ease in/out
        vw, vh = cw - (cw - W) * p, ch - (ch - H) * p              # view shrinks -> zoom in
        l, tp = (cw - vw) / 2, (ch - vh) / 2
        fr = np.asarray(self.canvas.resize((W, H), Image.BILINEAR, box=(l, tp, l + vw, tp + vh)), dtype=np.float32)
        a = self.alpha * min(1.0, max(0.0, (t - 0.35) / 0.6))      # caption fades in
        return fr + (self.rgb - fr) * a


# ---------------------------------------------------------------- main
def build_video(script: VideoScript, image_paths: List[str], output_path: str,
                bg_music_path: Optional[str] = None, log: Log = print, validated: bool = False) -> dict:
    images = image_paths if validated else load_images(image_paths, log)
    scenes_in = script.scenes
    n = len(scenes_in)
    photos = assign_images(n, images)
    tmp = tempfile.mkdtemp(prefix="pv_")
    ff = ffmpeg_exe()

    # 1) narration per scene -> scene length follows the voice
    log("Generating narration…")
    voices, engine = [], "none"
    for i, s in enumerate(scenes_in):
        path, eng = synthesize(s.voiceover, os.path.join(tmp, f"vo_{i}"))
        voices.append(path)
        if path:
            engine = eng
    if engine == "none":
        log("⚠ Narration unavailable (no TTS engine reachable) - video will have captions + music only.")
    else:
        log(f"   narration engine: {engine}")

    durs = []
    for s, v in zip(scenes_in, voices):
        need = (audio_duration(v) + VO_DELAY + 0.9) if v else s.duration_hint
        durs.append(max(MIN_DUR.get(s.scene_type, 4.0), need))
    starts, t0 = [], 0.0
    for d in durs:
        starts.append(t0)
        t0 += d - XFADE
    total = starts[-1] + durs[-1]

    # 2) frames -> ffmpeg (silent video)
    silent = os.path.join(tmp, "silent.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    enc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                            "-preset", "medium", "-b:v", "3500k", "-pix_fmt", "yuv420p", silent],
                           stdin=subprocess.PIPE)
    scenes = []
    nframes = int(round(total * FPS))
    try:
        for i, (s, ph, d) in enumerate(zip(scenes_in, photos, durs)):
            log(f"Preparing scene {i + 1}/{n} ({s.scene_type})…")
            scenes.append(_Scene(ph, s.caption, s.scene_type, d, i, n))
        log(f"Rendering {nframes} frames…")
        for f in range(nframes):
            t = f / FPS
            frame = None
            for i, sc in enumerate(scenes):                        # at most two scenes overlap
                lt = t - starts[i]
                if 0 <= lt < sc.dur:
                    img = sc.render(lt)
                    if frame is None:
                        frame = img
                    else:
                        w = min(1.0, lt / XFADE)                    # cross-dissolve the newer scene in
                        frame = frame * (1 - w) + img * w
            if frame is None:
                frame = np.zeros((H, W, 3), np.float32)
            fade = min(1.0, t / 0.6, (total - t) / 0.9)             # fade in / out
            enc.stdin.write((frame * max(0.0, fade)).astype(np.uint8).tobytes())
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError("ffmpeg failed while encoding frames")
    finally:
        if enc.poll() is None:
            enc.kill()

    # 3) audio: music bed + narration, muxed into the final MP4
    cmd, filt, labels, k = [ff, "-y", "-loglevel", "error", "-i", silent], [], [], 1
    if bg_music_path and os.path.exists(bg_music_path):
        cmd += ["-stream_loop", "-1", "-i", bg_music_path]
        filt.append(f"[{k}:a]atrim=0:{total:.2f},volume=0.16,afade=t=out:st={total - 2:.2f}:d=2[m]")
        labels.append("[m]"); k += 1
    for v, st in zip(voices, starts):
        if v:
            cmd += ["-i", v]
            ms = int((st + VO_DELAY) * 1000)
            filt.append(f"[{k}:a]adelay={ms}|{ms},volume=1.6[v{k}]")
            labels.append(f"[v{k}]"); k += 1
    if labels:
        filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
                    f"atrim=0:{total:.2f}[a]")
        cmd += ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-movflags", "+faststart", output_path]
    log(f"Encoding MP4 ({total:.0f}s)…")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg audio mux failed: " + r.stderr[-300:])
    return {"path": output_path, "duration": total, "scenes": n, "images_used": len(images), "narration": engine}
