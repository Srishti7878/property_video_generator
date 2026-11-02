#!/usr/bin/env python3
"""
AI Property Video Generator
CLI entry point – follows the Realty Assistant assignment requirements.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from generate_script import generate_script, print_script
from generate_video import generate_video

try:
    from generate_tts import generate_voiceover
    HAS_TTS = True
except ImportError:
    HAS_TTS = False
    def generate_voiceover(*args, **kwargs):
        raise RuntimeError("gTTS is not installed. Run: pip install gTTS")



def collect_input() -> dict:
    """Simple interactive form for property details and images."""
    print("\n========================================")
    print("   AI Property Video Generator")
    print("========================================\n")

    data = {}
    data["name"] = input("Property name          : ").strip() or "Beautiful Property"
    data["location"] = input("Location               : ").strip()
    data["price"] = input("Price (e.g. 1.25 Cr)   : ").strip()
    data["type"] = input("Property type          : ").strip()
    features_raw = input("Key features (comma separated): ").strip()
    data["features"] = [f.strip() for f in features_raw.split(",") if f.strip()]
    data["cta"] = input("Contact / CTA text     : ").strip() or "Call us today to schedule a viewing."

    print("\nEnter image paths (one per line). Press Enter on empty line when finished:")
    images = []
    while len(images) < 8:
        path = input(f"  Image {len(images)+1}: ").strip().strip('"')
        if not path:
            break
        images.append(path)
    data["images"] = images
    return data


def load_sample() -> dict:
    """Load the included sample property."""
    sample_path = Path(__file__).parent / "sample_data" / "sample_property.json"
    if sample_path.exists():
        with open(sample_path, encoding="utf-8") as f:
            return json.load(f)

    # Fallback if file is missing
    return {
        "name": "Sunrise Heights",
        "location": "Whitefield, Bangalore",
        "price": "₹1.25 Cr",
        "type": "3-BHK Apartment",
        "features": [
            "Spacious living room with balcony",
            "Modular kitchen with chimney",
            "Master bedroom with walk-in closet",
            "Clubhouse and swimming pool access",
            "24/7 security and power backup"
        ],
        "cta": "Call +91 98765 43210 to book a private tour today.",
        "images": []
    }


def validate(data: dict) -> list:
    """Return human-readable warnings."""
    messages = []
    if not data.get("name"):
        messages.append("Property name is empty – a default will be used.")
    images = data.get("images", [])
    if not images:
        messages.append("No images supplied. The video will contain only text cards.")
    else:
        missing = [p for p in images if not os.path.isfile(p)]
        if missing:
            messages.append(f"These image files were not found: {missing}")
    return messages


def main():
    parser = argparse.ArgumentParser(
        description="Generate a short promotional property video from details + images"
    )
    parser.add_argument("--sample", action="store_true", help="Use built-in sample data")
    parser.add_argument("--json", type=str, help="Path to a JSON file with property data")
    parser.add_argument("-o", "--output", default="output/property_video.mp4",
                        help="Output MP4 path (default: output/property_video.mp4)")
    parser.add_argument("--music", type=str, default=None,
                        help="Optional path to background music file (mp3/wav/aac)")
    parser.add_argument("--no-voice", action="store_true",
                        help="Skip voice-over narration")
    args = parser.parse_args()

    # ---- Collect data ----
    if args.sample:
        data = load_sample()
        print("Loaded sample property data.")
    elif args.json:
        if not os.path.isfile(args.json):
            print(f"Error: JSON file not found → {args.json}")
            sys.exit(1)
        with open(args.json, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = collect_input()

    # ---- Validate ----
    warnings = validate(data)
    for w in warnings:
        print(f"Warning: {w}")

    # ---- Generate script (facts only) ----
    script = generate_script(data)
    print_script(script)

    # ---- Generate voice-over (optional) ----
    voiceover_path = None
    if not args.no_voice and HAS_TTS:
        try:
            print("Generating voice-over narration...")
            voiceover_path = generate_voiceover(script["full_voiceover"])
            print("Voice-over ready.")
        except Exception as e:
            print(f"Warning: could not generate voice-over ({e}). Continuing without narration.")
    elif not args.no_voice and not HAS_TTS:
        print("Note: gTTS not installed – skipping voice-over. Run: pip install gTTS")

    # ---- Generate video ----
    try:
        video_path = generate_video(
            property_data=data,
            script=script,
            image_paths=data.get("images", []),
            output_path=args.output,
            background_music=args.music,
            voiceover_path=voiceover_path
        )
        print(f"\nDone! You can open the video here:\n{os.path.abspath(video_path)}")
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error while creating video: {e}")
        print("Please make sure ffmpeg is installed and available in your PATH.")
        sys.exit(1)
    finally:
        # Clean up temporary voice-over file
        if voiceover_path and os.path.exists(voiceover_path):
            try:
                os.remove(voiceover_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
