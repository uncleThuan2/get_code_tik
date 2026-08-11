import os
import json
import requests
import logging
from typing import Tuple, List
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_URL = "https://raw.githubusercontent.com/uncleThuan2/get_code_tik/main/sample/co_code_lon.png"
DEFAULT_STREAM_URL = "https://raw.githubusercontent.com/uncleThuan2/get_code_tik/main/screenshots/frame_1.png"


from app.storage.cloud_uploader import upload_temp_image_and_get_url

def extract_codes_via_gemini_vision(stream_data: bytes | Image.Image = None, api_key: str = None, stream_url: str = None) -> Tuple[List[str], List[str]]:
    """Extract small and large reward codes using Gemini 2.5 Flash Vision AI with 2 public URL image links."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_API_KEY environment variable not provided.")
        return [], []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"

    sample_url = os.getenv("SAMPLE_PUBLIC_URL", DEFAULT_SAMPLE_URL)
    stream_image_url = stream_url or (upload_temp_image_and_get_url(stream_data) if stream_data else DEFAULT_STREAM_URL)

    prompt = (
        "Image 1 (from URL link) is the reference sample UI layout showing where reward codes appear (yellow speech bubbles for small codes next to chests, and pink banner for large code). "
        "Image 2 (from URL link) is the live stream screenshot. Compare Image 2 against Image 1 and extract: "
        "1) All small reward codes visible in the yellow speech bubbles. "
        "2) The large reward code in the pink banner if released. If the pink banner says 'Sắp xuất hiện' or is not released, do not include it in large_codes. "
        "Return ONLY a valid JSON object with format: {\"small_codes\": [\"CODE1\", \"CODE2\"], \"large_codes\": [\"CODE3\"]}"
    )

    parts = [
        {"text": prompt},
        # Image 1 URL: Sample reference image link
        {
            "file_data": {
                "file_uri": sample_url,
                "mime_type": "image/png"
            }
        },
        # Image 2 URL: Stream screenshot image link
        {
            "file_data": {
                "file_uri": stream_image_url,
                "mime_type": "image/png"
            }
        }
    ]

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        res_json = response.json()

        if "error" in res_json:
            logger.error(f"Gemini API Error: {res_json['error']}")
            return [], []

        candidates = res_json.get("candidates", [])
        if candidates:
            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            logger.info(f"Gemini AI Raw Response: {content_text}")

            parsed = json.loads(content_text)
            small_codes = parsed.get("small_codes", [])
            large_codes = parsed.get("large_codes", [])

            small_codes = [s.strip().upper() for s in small_codes if isinstance(s, str) and s.strip()]
            large_codes = [l.strip().upper() for l in large_codes if isinstance(l, str) and l.strip()]

            return small_codes, large_codes

    except Exception as e:
        logger.error(f"Gemini Vision API call failed: {e}", exc_info=True)

    return [], []
