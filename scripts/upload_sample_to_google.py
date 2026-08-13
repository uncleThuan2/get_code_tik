import os
import sys
import json
import requests
from pathlib import Path

API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_SAMPLE_PATH = os.getenv("GEMINI_SAMPLE_IMAGE_PATH", "sample/co_code_lon.png")
IMAGE_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SAMPLE_PATH)

if not API_KEY:
    raise SystemExit("Missing GEMINI_API_KEY in environment")

if not IMAGE_PATH.exists():
    raise SystemExit(f"Image not found: {IMAGE_PATH}")

upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={API_KEY}"
headers = {"X-Goog-Upload-Protocol": "multipart"}
metadata = json.dumps({"file": {"display_name": IMAGE_PATH.name}})

with IMAGE_PATH.open("rb") as f:
    file_bytes = f.read()

files = {
    "metadata": ("metadata.json", metadata, "application/json; charset=UTF-8"),
    "file": (IMAGE_PATH.name, file_bytes, "image/png"),
}

resp = requests.post(upload_url, headers=headers, files=files, timeout=30)
print(resp.status_code)
print(resp.text)

try:
    data = resp.json()
    uri = data.get("file", {}).get("uri")
    name = data.get("file", {}).get("name")
    if uri:
        print("\nFILE_URI=" + uri)
        print("FILE_NAME=" + name)
        print("\nSET THIS ENV VAR:")
        print(f"GEMINI_SAMPLE_IMAGE_URI={uri}")
except Exception:
    pass
