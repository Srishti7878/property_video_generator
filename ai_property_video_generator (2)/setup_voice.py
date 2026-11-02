"""Download a free offline Piper voice (~60 MB) into assets/voices/ (optional)."""
import io, sys, tarfile, urllib.request
from pathlib import Path

URL = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-lessac-medium.tar.gz"
dest = Path(__file__).parent / "assets" / "voices"
dest.mkdir(parents=True, exist_ok=True)
print("Downloading", URL)
data = urllib.request.urlopen(URL, timeout=120).read()
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    t.extractall(dest)
print("Voice installed in", dest)
