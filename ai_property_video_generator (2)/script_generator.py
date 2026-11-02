"""
script_generator.py
Script + caption generation. Uses ONLY facts supplied in the input.

* Template mode (default, offline, deterministic) - always works.
* LLM mode (optional, needs GEMINI_API_KEY or OPENAI_API_KEY) - output is
  fact-checked against the input and discarded if it introduces new numbers
  or amenities; the template is used instead.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

from dataclasses import dataclass, field


class UserInputError(Exception):
    """Raised for problems the user can fix (bad / missing input)."""


def _clean(v) -> str:
    return "" if v is None else str(v).strip()


@dataclass
class PropertyInput:
    name: str
    location: str
    price: str = ""                      # optional
    property_type: str = "Apartment"
    features: List[str] = field(default_factory=list)
    cta: str = "Contact us today to book a site visit."
    contact: str = ""                    # optional

    def __post_init__(self):
        for k in ("name", "location", "price", "property_type", "cta", "contact"):
            setattr(self, k, _clean(getattr(self, k)))
        f = self.features
        if isinstance(f, str):
            f = re.split(r"[,\n;]", f)
        self.features = [str(x).strip() for x in (f or []) if str(x).strip()]
        if not self.property_type:
            self.property_type = "Apartment"
        if not self.cta:
            self.cta = "Contact us today to book a site visit."


@dataclass
class SceneScript:
    scene_type: str            # intro | feature | outro
    caption: str
    voiceover: str
    duration_hint: float = 5.0


@dataclass
class VideoScript:
    title: str
    scenes: List[SceneScript]

    @property
    def full_voiceover(self) -> str:
        return " ".join(s.voiceover for s in self.scenes)


def validate_property(data: dict) -> PropertyInput:
    """Build PropertyInput; name and location are required."""
    fields = ("name", "location", "price", "property_type", "features", "cta", "contact")
    prop = PropertyInput(**{k: data.get(k) for k in fields if data.get(k) is not None}) \
        if _clean(data.get("name")) and _clean(data.get("location")) else None
    if prop is None:
        missing = [k for k in ("name", "location") if not _clean(data.get(k))]
        raise UserInputError("Missing property details: " + ", ".join(missing)
                             + ". Property name and location are required.")
    return prop


# --------------------------------------------------------------------------
# Template script
# --------------------------------------------------------------------------
def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".!")
    return text[:1].upper() + text[1:] + "."


def generate_template_script(prop: PropertyInput, max_feature_scenes: int = 5) -> VideoScript:
    name, loc = prop.name, prop.location
    ptype = prop.property_type or "property"

    intro_voice = f"Welcome to {name}. {_sentence(f'{_article(ptype).capitalize()} {ptype.lower()} in {loc}')}"
    if prop.price:
        intro_voice += f" {_sentence('Priced at ' + prop.price)}"
    intro_cap = [name, f"{ptype}  |  {loc}"]
    if prop.price:
        intro_cap.append(prop.price)

    scenes = [SceneScript(scene_type="intro", caption="\n".join(intro_cap),
                          voiceover=intro_voice, duration_hint=6.0)]

    feats = prop.features
    n = min(len(feats), max(1, max_feature_scenes))
    if feats:
        # spread features over n scenes, keeping order (1 feature per scene when possible)
        chunks: List[List[str]] = [[] for _ in range(n)]
        for i, f in enumerate(feats):
            chunks[min(i * n // len(feats), n - 1)].append(f)
        for chunk in chunks:
            scenes.append(SceneScript(
                scene_type="feature",
                caption="  •  ".join(chunk),
                voiceover=" ".join(_sentence(c) for c in chunk),
                duration_hint=4.5,
            ))
    else:
        scenes.append(SceneScript(scene_type="feature", caption=f"Discover {name}",
                                  voiceover=f"Discover {name}.", duration_hint=4.0))

    cap = [prop.cta] + ([prop.contact] if prop.contact else [])
    voice = _sentence(prop.cta) + (f" {prop.contact}." if prop.contact else "")
    scenes.append(SceneScript(scene_type="outro", caption="\n".join(cap),
                              voiceover=voice, duration_hint=6.0))
    return VideoScript(title=f"{name} - {loc}", scenes=scenes)


# --------------------------------------------------------------------------
# Optional LLM script (fact-checked)
# --------------------------------------------------------------------------
_PROMPT = """You are a real-estate copywriter. Write a short promo video script.
STRICT RULES: use ONLY the facts below. Do NOT invent amenities, rooms, views,
distances, prices or phone numbers. Max ~100 spoken words. Output exactly:

1. INTRO | <caption> | <voiceover>
2. FEATURE | <caption> | <voiceover>
...
N. OUTRO | <caption> | <voiceover>

Name: {name}
Location: {location}
Type: {ptype}
Price: {price}
Features: {features}
CTA: {cta}
Contact: {contact}
"""


def _facts_ok(script: VideoScript, prop: PropertyInput) -> bool:
    """Reject LLM output that contains numbers not present in the input."""
    src = " ".join([prop.name, prop.location, prop.price, prop.property_type,
                    " ".join(prop.features), prop.cta, prop.contact])
    allowed = set(re.findall(r"\d+", src))
    used = set(re.findall(r"\d+", " ".join(s.voiceover + " " + s.caption for s in script.scenes)))
    return used <= allowed


def generate_llm_script(prop: PropertyInput) -> Optional[VideoScript]:
    gem, oai = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"), os.getenv("OPENAI_API_KEY")
    if not (gem or oai):
        return None
    prompt = _PROMPT.format(name=prop.name, location=prop.location, ptype=prop.property_type,
                            price=prop.price or "not provided",
                            features="; ".join(prop.features) or "none provided",
                            cta=prop.cta, contact=prop.contact or "not provided")
    try:
        if gem:
            import google.generativeai as genai
            genai.configure(api_key=gem)
            text = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash")).generate_content(prompt).text
        else:
            from openai import OpenAI
            r = OpenAI(api_key=oai).chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=500)
            text = r.choices[0].message.content
        scenes = []
        for m in re.finditer(r"^\s*\d+\.\s*(INTRO|FEATURE|OUTRO)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$",
                             text, re.I | re.M):
            t = m.group(1).lower()
            scenes.append(SceneScript(scene_type=t, caption=m.group(2), voiceover=m.group(3),
                                      duration_hint=6.0 if t != "feature" else 4.5))
        if len(scenes) < 3 or scenes[0].scene_type != "intro" or scenes[-1].scene_type != "outro":
            return None
        script = VideoScript(title=f"{prop.name} - {prop.location}", scenes=scenes)
        return script if _facts_ok(script, prop) else None
    except Exception as e:
        print(f"[script] LLM failed ({e}); using template.")
        return None


def generate_script(prop: PropertyInput, prefer_llm: bool = False, max_feature_scenes: int = 5) -> VideoScript:
    if prefer_llm:
        s = generate_llm_script(prop)
        if s:
            print("[script] Using LLM script (fact-checked).")
            return s
    print("[script] Using template script.")
    return generate_template_script(prop, max_feature_scenes)
