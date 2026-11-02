"""
Generate voice-over narration using gTTS (Google Text-to-Speech).
Uses only the script text that was created from the supplied facts.
"""

import os
import tempfile
from typing import Optional

from gtts import gTTS


def generate_voiceover(text: str, output_path: Optional[str] = None, lang: str = "en") -> str:
    """
    Convert the given text into an MP3 voice-over file.
    Returns the path to the generated audio file.
    """
    if not text or not text.strip():
        raise ValueError("No text provided for voice-over")

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        output_path = tmp.name
        tmp.close()

    # Clean text a bit for better speech
    clean = text.replace("Rs.", "Rupees").replace("₹", "Rupees")
    clean = clean.replace("–", " ").replace("-", " ")

    tts = gTTS(text=clean, lang=lang, slow=False)
    tts.save(output_path)
    return output_path
