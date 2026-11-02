# AI Property Video Generator

**Track:** AI Content Creation / Multimedia  
**Assignment:** Realty Assistant – AI & Machine Learning Assignments

## Problem Solved
Real estate teams have property photos and basic details, but creating a promotional video for every property takes time. This tool automatically turns property information + images into a short, ready-to-share MP4 video (20–40 seconds).

## What This Solution Does
- Accepts property details and 4–8 images via CLI or JSON
- Generates a short voice-over script and captions using **only the facts supplied** (template logic)
- Arranges images into scenes with readable text overlays and fade transitions
- Exports a final MP4 video
- Handles missing images or missing details gracefully with clear error messages

## Requirements
- Python 3.9+
- ffmpeg (must be installed)

### Install ffmpeg
**Windows:**
1. Download from https://www.gyan.dev/ffmpeg/builds/ (get the full build)
2. Extract and add the `bin` folder to your system PATH
3. Or use: `winget install ffmpeg`

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Installation
```bash
pip install -r requirements.txt
```

## How to Run

### Option 1 – Interactive mode
```bash
python main.py
```
You will be asked for property name, location, price, type, features, CTA text, and image paths.

### Option 2 – Sample data (quick demo)
```bash
python main.py --sample
```

### Option 3 – From JSON file
```bash
python main.py --json sample_data/sample_property.json
```

## Output
- Generated video is saved in the `output/` folder
- A sample video is already included: `output/sample_property_video.mp4`

## Project Structure
```
property-video-generator/
├── main.py                 # CLI entry point
├── generate_script.py      # Script & caption generation (template-based)
├── generate_video.py       # Video assembly using ffmpeg
├── requirements.txt
├── README.md
├── sample_data/
│   ├── sample_property.json
│   └── img1.jpg … img4.jpg
└── output/
    └── sample_property_video.mp4
```

## Approach & Key Decisions
1. **Script generation** uses clear template logic (not an external LLM) so every word is based only on the facts the user supplies. This keeps the video factual and avoids hallucination.
2. **Video assembly** is done with ffmpeg for reliability and high quality.
3. **Scenes**: Title card → Opening text → Image scenes with feature captions → Final CTA card.
4. **Error handling**: Missing images or fields produce clear messages instead of crashes.
5. No API keys or paid services are required.

## AI / Libraries / External Services Used
- **Pillow** – image resizing and text card generation
- **ffmpeg** – video encoding, transitions, and concatenation
- Pure Python template logic for script (no external AI model)

## Limitations
- Voice-over narration is prepared as text but not spoken by default (can be extended with TTS).
- Background music is optional and not included in the base version.
- Designed as a working prototype, not a production enterprise system.

## How We Meet the Evaluation Criteria
| Criterion                              | How it is met                                      |
|----------------------------------------|----------------------------------------------------|
| Problem understanding                  | Directly solves the real-estate video creation gap |
| Working implementation                 | Fully runnable CLI that produces a real MP4        |
| AI/ML approach                         | Clean template logic + clear explanation           |
| Code quality & reliability             | Modular files, error handling, comments            |
| Usability, demo & explanation          | Sample data + sample video + clear README          |

## Extra Options Added

- `--music path/to/file.mp3` : optional background music (low volume, auto-fades)
- `run.bat` : Windows double-click launcher (installs deps + runs sample)

These keep the solution fully compliant with the assignment while making the video more polished.

## Step 1 Improvement: Voice-over Narration

The tool now generates a spoken voice-over using **gTTS** (Google Text-to-Speech).

- Narration is created from the same factual script (no extra invented text).
- To disable voice-over: `python main.py --sample --no-voice`
- Requires internet only for the first generation of the audio.

Install the extra dependency:
```bash
pip install gTTS
```

## Step 2 Improvement: Background Music

- If you provide a music file: `python main.py --sample --music yourmusic.mp3`
- If no music file is given, a soft ambient background tone is automatically generated and mixed under the voice-over.
- Volume is kept low so the narration remains clear.

## Step 3 Improvement: Visual Design

- Cleaner dark theme with accent bars
- Price badge on every property image
- Better caption bars with accent line
- More professional overall look

## Step 4: Web Interface (Streamlit)

Run the browser UI with:

```bash
streamlit run app.py
```

Then open the local URL shown in the terminal (usually http://localhost:8501).

You can fill the form, upload images, generate the video, preview it, and download the MP4 – all from the browser.
