"""
Generate a short, factual voice-over script and captions
using ONLY the property details supplied by the user.
No external AI model is used – pure template logic.
"""

from typing import Dict, List


def generate_script(property_data: Dict) -> Dict:
    """
    Create a structured script from property details.

    Returns a dictionary with:
        title, opening, scenes, cta, full_voiceover
    """
    name = str(property_data.get("name", "Property")).strip() or "Property"
    location = str(property_data.get("location", "")).strip()
    price = str(property_data.get("price", "")).strip()
    prop_type = str(property_data.get("type", "")).strip()
    features = property_data.get("features", [])
    cta = str(property_data.get("cta", "")).strip()

    # Normalize features
    if isinstance(features, str):
        features = [f.strip() for f in features.split(",") if f.strip()]
    features = [str(f).strip() for f in features if str(f).strip()]

    # ---- Title ----
    if prop_type:
        title = f"{prop_type} – {name}"
    else:
        title = name

    # ---- Opening sentence (facts only) ----
    parts = []
    if prop_type:
        parts.append(f"Discover this beautiful {prop_type}")
    else:
        parts.append("Discover this beautiful property")
    if location:
        parts.append(f"located in {location}")
    if price:
        parts.append(f"priced at {price}")
    opening = " ".join(parts) + "."

    # ---- Feature scenes ----
    scenes = []
    if features:
        for feat in features[:5]:          # maximum 5 feature scenes
            scenes.append({
                "caption": feat,
                "duration": 4.0
            })
    else:
        scenes.append({
            "caption": "Modern living spaces",
            "duration": 4.0
        })

    # ---- Closing CTA ----
    if not cta:
        cta = "Contact us today to schedule a private viewing."
    closing = cta

    # Full voice-over text (ready for optional TTS)
    voice_parts = [opening]
    if features:
        voice_parts.append("Key highlights include: " + ", ".join(features[:4]) + ".")
    voice_parts.append(closing)
    full_voiceover = " ".join(voice_parts)

    return {
        "title": title,
        "opening": opening,
        "scenes": scenes,
        "cta": closing,
        "full_voiceover": full_voiceover
    }


def print_script(script: Dict) -> None:
    """Pretty-print the generated script for the user."""
    print("\n=== Generated Script (facts only) ===")
    print(f"Title   : {script['title']}")
    print(f"Opening : {script['opening']}")
    print("Scenes  :")
    for i, s in enumerate(script["scenes"], 1):
        print(f"  {i}. {s['caption']}  ({s['duration']}s)")
    print(f"CTA     : {script['cta']}")
    print("=====================================\n")
