import os
import io
import json
import base64
import requests
import logging
from typing import Tuple, List
from PIL import Image

logger = logging.getLogger(__name__)

# Public GitHub raw URL for sample image
SAMPLE_PUBLIC_URL = "https://raw.githubusercontent.com/uncleThuan2/get_code_tik/main/sample/co_code_lon.png"


def image_to_base64(pil_img: Image.Image) -> str:
    """Convert in-memory screenshot PIL Image to Base64 bytes."""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def extract_codes_via_gemini_vision(stream_img: Image.Image, api_key: str = None) -> Tuple[List[str], List[str]]:
    """Extract small and large reward codes using Gemini 2.5 Flash Vision AI:
    - Image 1: Public GitHub URL link for sample reference image
    - Image 2: Newly captured stream screenshot (in-memory bytes)
    - Prompt: Extraction instruction
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_API_KEY environment variable not provided.")
        return [], []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"

    stream_b64 = image_to_base64(stream_img)

    prompt = (
        "Image 1 (from URL link) is the reference sample UI layout showing where reward codes appear (yellow speech bubbles for small codes next to chests, and pink banner for large code). "
        "Image 2 is the live stream screenshot. Compare Image 2 against Image 1 and extract: "
        "1) All small reward codes visible in the yellow speech bubbles. "
        "2) The large reward code in the pink banner if released. If the pink banner says 'Sắp xuất hiện' or is not released, do not include it in large_codes. "
        "Return ONLY a valid JSON object with format: {\"small_codes\": [\"CODE1\", \"CODE2\"], \"large_codes\": [\"CODE3\"]}"
    )

    parts = [
        {"text": prompt},
        # Image 1: Public GitHub URL link for sample reference image
        {
            "file_data": {
                "file_uri": SAMPLE_PUBLIC_URL,
                "mime_type": "image/png"
            }
        },
        # Image 2: Newly captured stream screenshot from RAM
        {
            "inline_data": {
                "mime_type": "image/png",
                "data": stream_b64
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
            # Fallback to local sample image if file_uri URL fails
            return _fallback_with_local_sample(url, headers, stream_b64, prompt)

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


def _fallback_with_local_sample(url: str, headers: dict, stream_b64: str, prompt: str) -> Tuple[List[str], List[str]]:
    """Fallback using local sample image base64 if URL link is restricted."""
    sample_path = "sample/co_code_lon.png"
    if not os.path.exists(sample_path):
        return [], []

    with open(sample_path, "rb") as f:
        sample_b64 = base64.b64encode(f.read()).decode("utf-8")

    parts = [
        {"text": prompt},
        {"inline_data": {"mime_type": "image/png", "data": sample_b64}},
        {"inline_data": {"mime_type": "image/png", "data": stream_b64}}
    ]

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        res_json = response.json()
        candidates = res_json.get("candidates", [])
        if candidates:
            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            parsed = json.loads(content_text)
            small_codes = [s.strip().upper() for s in parsed.get("small_codes", []) if isinstance(s, str) and s.strip()]
            large_codes = [l.strip().upper() for l in parsed.get("large_codes", []) if isinstance(l, str) and l.strip()]
            return small_codes, large_codes
    except Exception:
        pass

    return [], []
