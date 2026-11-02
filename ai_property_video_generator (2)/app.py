#!/usr/bin/env python3
"""
AI Property Video Generator.

  python app.py                                   # CLI, bundled Homeland Mohali sample
  python app.py --property my.json --out out.mp4  # CLI, your own listing (JSON + image paths)
  python app.py --name "Homeland Mohali" --location "Kharar, Mohali" --features "A, B, C" --images a.jpg b.jpg ...
  streamlit run app.py                            # web form with preview + download
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable, List

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from script_generator import PropertyInput, UserInputError, generate_script, validate_property  # noqa: E402
from tts_engine import get_bg_music  # noqa: E402
from video_engine import build_video, load_images  # noqa: E402

SAMPLE_JSON = ROOT / "sample_data" / "homeland_mohali.json"


def run_pipeline(prop: PropertyInput, image_paths: List[str], output_path: str,
                 prefer_llm: bool = False, log: Callable[[str], None] = print) -> dict:
    images = load_images(image_paths, log)                       # fail fast with a clear message
    n_mid = max(1, len(images) - 2) if len(images) >= 3 else len(images)
    log("Writing script (using only the supplied facts)…")
    script = generate_script(prop, prefer_llm=prefer_llm, max_feature_scenes=min(5, n_mid))
    info = build_video(script, images, output_path, bg_music_path=get_bg_music(), log=log, validated=True)
    info["script"] = script
    return info


def load_property_file(path: str):
    p = Path(path)
    if not p.is_file():
        raise UserInputError(f"Property file not found: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise UserInputError(f"{path} is not valid JSON: {e}")
    imgs = [str((p.parent / i) if not os.path.isabs(i) else i) for i in data.get("images", [])]
    return data, imgs


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Turn property details + photos into a promo MP4.")
    ap.add_argument("--property", help="JSON file with details (+ optional 'images' list)")
    ap.add_argument("--name"); ap.add_argument("--location"); ap.add_argument("--price", default="")
    ap.add_argument("--type", dest="property_type", default="Apartment")
    ap.add_argument("--features", default="", help="comma-separated")
    ap.add_argument("--cta", default="Contact us today to book a site visit.")
    ap.add_argument("--contact", default="")
    ap.add_argument("--images", nargs="*", help="image files or a folder (in scene order)")
    ap.add_argument("--out", default=str(ROOT / "output" / "homeland_mohali_promo.mp4"))
    ap.add_argument("--llm", action="store_true", help="use Gemini/OpenAI for the script if a key is set")
    args, _ = ap.parse_known_args(argv)

    try:
        if args.name or args.location:
            data, imgs = {k: getattr(args, k) for k in
                          ("name", "location", "price", "property_type", "features", "cta", "contact")}, []
        else:
            data, imgs = load_property_file(args.property or SAMPLE_JSON)
        if args.images:
            imgs = []
            for a in args.images:
                imgs += sorted(str(f) for f in Path(a).iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")) \
                    if Path(a).is_dir() else [a]
        prop = validate_property(data)
        info = run_pipeline(prop, imgs, args.out, prefer_llm=args.llm)
    except UserInputError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # unexpected - still no stack trace for the user
        print(f"\nERROR: video could not be generated ({type(e).__name__}: {e}).\n"
              "Check that ffmpeg works and dependencies are installed (pip install -r requirements.txt).",
              file=sys.stderr)
        return 1
    print(f"\n✔ {info['path']}  ({info['duration']:.0f}s, {info['scenes']} scenes, narration: {info['narration']})")
    return 0


# ------------------------------------------------------------------ Streamlit
def streamlit_app():
    import streamlit as st
    st.set_page_config(page_title="AI Property Video Generator", page_icon="🏠", layout="wide")
    st.title("🏠 AI Property Video Generator")
    st.caption("Property details + photos → ready-to-share MP4. Only the facts you enter are used.")
    sample, sample_imgs = load_property_file(SAMPLE_JSON)

    if st.sidebar.button("Load Homeland Mohali sample"):
        st.session_state["use_sample"] = True
    d = sample if st.session_state.get("use_sample") else {}
    prefer_llm = st.sidebar.toggle("Use LLM for script (needs API key)", value=False)

    c1, c2 = st.columns(2)
    name = c1.text_input("Property name *", d.get("name", ""))
    location = c1.text_input("Location *", d.get("location", ""))
    ptype = c1.text_input("Property type", d.get("property_type", "Apartment"))
    price = c1.text_input("Price (optional)", d.get("price", ""))
    feats = c2.text_area("Key features (one per line or comma-separated)", "\n".join(d.get("features", [])), height=150)
    cta = c2.text_input("Call to action", d.get("cta", "Contact us today to book a site visit."))
    contact = c2.text_input("Contact (optional)", d.get("contact", ""))

    ups = st.file_uploader("Property photos (4–8, shown in the order uploaded)", type=["jpg", "jpeg", "png", "webp"],
                           accept_multiple_files=True)
    use_sample_imgs = st.session_state.get("use_sample") and not ups
    if use_sample_imgs:
        st.info("No upload - using the 6 real Homeland Mohali photos bundled with the project.")

    if st.button("🎬 Generate video", type="primary", use_container_width=True):
        try:
            prop = validate_property(dict(name=name, location=location, property_type=ptype, price=price,
                                          features=feats, cta=cta, contact=contact))
            tmp = tempfile.mkdtemp(prefix="up_")
            paths = []
            for i, u in enumerate(ups or []):
                p = os.path.join(tmp, f"{i:02d}_{Path(u.name).name}")
                Path(p).write_bytes(u.getbuffer()); paths.append(p)
            if use_sample_imgs:
                paths = sample_imgs
            if not paths:
                raise UserInputError("Please upload at least one property photo.")
            box = st.empty()
            out = ROOT / "output" / (("".join(c if c.isalnum() else "_" for c in name)[:40] or "property") + "_promo.mp4")
            with st.spinner("Rendering…"):
                info = run_pipeline(prop, paths, str(out), prefer_llm, log=lambda m: box.write(m))
            box.empty()
            st.success(f"Done - {info['duration']:.0f}s video, {info['scenes']} scenes")
            st.video(str(out))
            st.download_button("⬇ Download MP4", out.read_bytes(), out.name, "video/mp4", use_container_width=True)
            with st.expander("Script used"):
                for s in info["script"].scenes:
                    st.markdown(f"**{s.scene_type.upper()}** - {s.caption.replace(chr(10), ' / ')}  \n_{s.voiceover}_")
        except UserInputError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Video could not be generated: {e}")


def _in_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if _in_streamlit():
    streamlit_app()
elif __name__ == "__main__":
    sys.exit(cli())
