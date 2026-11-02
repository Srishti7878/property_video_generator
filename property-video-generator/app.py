"""
AI Property Video Generator – Web Interface
Simple Streamlit form for the Realty Assistant assignment.
"""

import os
import tempfile
from pathlib import Path

import streamlit as st

from generate_script import generate_script
from generate_video import generate_video

try:
    from generate_tts import generate_voiceover
    HAS_TTS = True
except ImportError:
    HAS_TTS = False


st.set_page_config(
    page_title="AI Property Video Generator",
    page_icon="🏠",
    layout="centered",
)

st.title("AI Property Video Generator")
st.caption("Realty Assistant – AI Content Creation / Multimedia Track")

st.markdown(
    "Enter property details and upload 4–8 images. "
    "The tool will create a short promotional MP4 using only the facts you provide."
)

with st.form("property_form"):
    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input("Property Name *", value="Sunrise Heights")
        location = st.text_input("Location", value="Whitefield, Bangalore")
        price = st.text_input("Price", value="Rs. 1.25 Cr")

    with col2:
        prop_type = st.text_input("Property Type", value="3-BHK Apartment")
        cta = st.text_input(
            "Contact / CTA text",
            value="Call +91 98765 43210 to book a private tour today.",
        )

    features_raw = st.text_area(
        "Key Features (one per line or comma-separated)",
        value="Spacious living room with balcony\nModular kitchen with chimney\nMaster bedroom with walk-in closet\nClubhouse and swimming pool access\n24/7 security and power backup",
        height=120,
    )

    uploaded_files = st.file_uploader(
        "Property Images (4–8 recommended)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )

    use_voice = st.checkbox("Add voice-over narration", value=True)
    submitted = st.form_submit_button("Generate Video", type="primary")

if submitted:
    if not name.strip():
        st.error("Property name is required.")
        st.stop()

    if not uploaded_files:
        st.warning("No images uploaded. The video will only contain text cards.")
    elif len(uploaded_files) > 8:
        st.warning("More than 8 images uploaded. Only the first 8 will be used.")

    # Parse features
    features = []
    for line in features_raw.replace(",", "\n").splitlines():
        line = line.strip()
        if line:
            features.append(line)

    data = {
        "name": name.strip(),
        "location": location.strip(),
        "price": price.strip(),
        "type": prop_type.strip(),
        "features": features,
        "cta": cta.strip() or "Contact us today to schedule a viewing.",
    }

    # Save uploaded images to temp files
    image_paths = []
    temp_dir = tempfile.mkdtemp()
    for i, uf in enumerate(uploaded_files[:8]):
        ext = Path(uf.name).suffix or ".jpg"
        path = os.path.join(temp_dir, f"img_{i}{ext}")
        with open(path, "wb") as f:
            f.write(uf.getbuffer())
        image_paths.append(path)

    data["images"] = image_paths

    with st.spinner("Generating script and video... this may take 20–40 seconds"):
        try:
            script = generate_script(data)

            voiceover_path = None
            if use_voice and HAS_TTS:
                try:
                    voiceover_path = generate_voiceover(script["full_voiceover"])
                except Exception as e:
                    st.warning(f"Voice-over skipped: {e}")

            output_path = os.path.join(temp_dir, "property_video.mp4")
            video_path = generate_video(
                property_data=data,
                script=script,
                image_paths=image_paths,
                output_path=output_path,
                voiceover_path=voiceover_path,
            )

            st.success("Video generated successfully!")

            # Show script summary
            with st.expander("Generated Script (facts only)"):
                st.write(f"**Title:** {script['title']}")
                st.write(f"**Opening:** {script['opening']}")
                st.write("**Scenes:**")
                for s in script["scenes"]:
                    st.write(f"- {s['caption']}")
                st.write(f"**CTA:** {script['cta']}")

            # Video preview + download
            st.video(video_path)

            with open(video_path, "rb") as f:
                st.download_button(
                    label="Download MP4",
                    data=f,
                    file_name="property_video.mp4",
                    mime="video/mp4",
                )

        except Exception as e:
            st.error(f"Error while creating video: {e}")
            st.info("Make sure ffmpeg is installed and available in your system PATH.")

st.markdown("---")
st.caption(
    "Built for the Realty Assistant AI & Machine Learning assignment. "
    "Script uses only the facts you supply. No external paid AI APIs required."
)
