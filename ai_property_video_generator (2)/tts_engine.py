"""
tts_engine.py - narration + royalty-free background music.

Narration engines, tried in order (first that works wins; flite = basic offline voice bundled in most ffmpeg builds):
  1. edge-tts  (Microsoft neural voices, free, needs internet)
  2. Piper     (offline neural voice; run `python setup_voice.py` once)
  3. gTTS      (needs internet)
4. flite     (robotic offline voice built into some ffmpeg builds - last resort)
If all fail the video is still produced (captions + music, no narration).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).parent
EDGE_VOICE = os.getenv("EDGE_VOICE", "en-IN-NeerjaNeural")
_piper_voice = None
_failed: set = set()


def _edge(text: str, out: str) -> bool:
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, EDGE_VOICE, rate="-4%").save(out))
    return os.path.exists(out) and os.path.getsize(out) > 500


def _find_piper_model() -> Optional[Path]:
    env = os.getenv("PIPER_MODEL")
    if env and Path(env).exists():
        return Path(env)
    found = sorted((ROOT / "assets" / "voices").glob("*.onnx"))
    return found[0] if found else None


def _piper(text: str, out: str) -> bool:
    global _piper_voice
    model = _find_piper_model()
    if model is None:
        return False
    from piper import PiperVoice
    if _piper_voice is None:
        cfg = Path(str(model) + ".json")
        _piper_voice = PiperVoice.load(str(model), config_path=str(cfg) if cfg.exists() else None)
    with wave.open(out, "wb") as w:
        _piper_voice.synthesize_wav(text, w)
    return os.path.getsize(out) > 500


def _gtts(text: str, out: str) -> bool:
    from gtts import gTTS
    gTTS(text=text, lang="en", tld="co.in").save(out)
    return os.path.getsize(out) > 500


def _flite(text: str, out: str) -> bool:
    """Last-resort robotic voice, only if the local ffmpeg was built with libflite."""
    tf = out + ".txt"
    Path(tf).write_text(text, encoding="utf-8")
    r = subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"flite=textfile={tf}:voice=slt", out], capture_output=True)
    os.remove(tf)
    return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 500


def synthesize(text: str, out_base: str) -> Tuple[Optional[str], str]:
    """Return (audio_path or None, engine_name)."""
    if not text.strip():
        return None, "none"
    for name, fn, ext in (("edge-tts", _edge, ".mp3"), ("piper", _piper, ".wav"), ("gTTS", _gtts, ".mp3")) + \
            (("flite", _flite, ".wav"),):
        if name in _failed:
            continue
        out = out_base + ext
        try:
            if fn(text, out):
                return out, name
        except Exception as e:
            print(f"[tts] {name} unavailable ({type(e).__name__}); trying next engine.")
            _failed.add(name)
    return None, "none"


def ffmpeg_exe() -> str:
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def audio_duration(path: str) -> float:
    r = subprocess.run([ffmpeg_exe(), "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    import re
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


# ---------------------------------------------------------------------------
# Royalty-free background music (generated, so there is no licence to worry about)
# ---------------------------------------------------------------------------
def generate_bg_music(path: str, seconds: int = 60) -> str:
    import numpy as np
    sr = 44100
    n = sr * seconds
    t = np.arange(n) / sr
    chords = [  # Cmaj7 - Am7 - Fmaj7 - G6   (soft, warm)
        [261.63, 329.63, 392.00, 493.88], [220.00, 261.63, 329.63, 392.00],
        [174.61, 261.63, 329.63, 440.00], [196.00, 246.94, 293.66, 329.63],
    ]
    bar = 4.0
    out = np.zeros(n)
    for b in range(int(seconds / bar)):
        s0, s1 = int(b * bar * sr), int((b + 1) * bar * sr)
        tt = t[s0:s1] - t[s0]
        env = np.minimum(1, tt / 1.2) * np.minimum(1, (bar - tt) / 1.2)
        for f in chords[b % 4]:
            out[s0:s1] += env * (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * 2 * f * tt)) * 0.06
        for k, f in enumerate(chords[b % 4] * 2):          # gentle plucks
            st = int(k * 0.5 * sr)
            L = min(int(1.4 * sr), s1 - s0 - st)
            if L <= 0:
                continue
            x = np.arange(L) / sr
            out[s0 + st:s0 + st + L] += np.sin(2 * np.pi * f * 2 * x) * np.exp(-3.2 * x) * 0.05
    out /= max(1e-9, np.abs(out).max()) / 0.8
    pcm = (out * 32767).astype(np.int16)
    tmp = path + ".wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", tmp,
                    "-af", "aecho=0.8:0.7:400:0.3", "-b:a", "128k", path], check=True)
    os.remove(tmp)
    return path


def get_bg_music() -> Optional[str]:
    """Use a user-supplied track in assets/, otherwise generate one once."""
    assets = ROOT / "assets"
    for n in ("ambient_bg.mp3", "background.mp3", "bg_music.mp3"):
        if (assets / n).exists():
            return str(assets / n)
    try:
        return generate_bg_music(str(assets / "ambient_bg.mp3"))
    except Exception as e:
        print(f"[tts] background music skipped: {e}")
        return None
