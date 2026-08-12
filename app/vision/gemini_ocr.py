import os
import io
import json
import base64
import requests
import logging
from typing import Tuple, List
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_PATH = "sample/co_code_lon.png"


def upload_to_google_file_api(img_data: bytes | Image.Image, api_key: str) -> Tuple[str, str]:
    """Upload screenshot image to official Google File API using GEMINI_API_KEY.

    Returns:
        (file_name: str, file_uri: str) e.g. ("files/abc123xyz", "https://generativelanguage.googleapis.com/files/abc123xyz")
    """
    try:
        if isinstance(img_data, Image.Image):
            buf = io.BytesIO()
            img_data.save(buf, format="PNG")
            img_bytes = buf.getvalue()
        else:
            img_bytes = img_data

        upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
        
        # Resumable / Multipart Upload Protocol for Google File API
        headers = {
            "X-Goog-Upload-Protocol": "multipart"
        }
        
        metadata = json.dumps({"file": {"display_name": "stream_frame.png"}})
        
        files = {
            "metadata": ("metadata.json", metadata, "application/json; charset=UTF-8"),
            "file": ("stream_frame.png", img_bytes, "image/png")
        }

        logger.info("Uploading screenshot directly to Google File API...")
        response = requests.post(upload_url, headers=headers, files=files, timeout=20)
        res_json = response.json()

        if response.status_code == 200 and "file" in res_json:
            file_info = res_json["file"]
            file_name = file_info.get("name", "")  # "files/abc123xyz"
            file_uri = file_info.get("uri", "")   # "https://generativelanguage.googleapis.com/files/abc123xyz"
            logger.info(f"Google File API Upload Success: {file_name} -> {file_uri}")
            return file_name, file_uri
        else:
            logger.error(f"Google File API Upload Failed: {res_json}")

    except Exception as e:
        logger.error(f"Google File API upload exception: {e}", exc_info=True)

    return "", ""


def delete_from_google_file_api(file_name: str, api_key: str):
    """Delete uploaded screenshot file from Google File API server immediately after process finishes."""
    if not file_name:
        return

    try:
        delete_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
        logger.info(f"Deleting temporary file {file_name} from Google File API...")
        response = requests.delete(delete_url, timeout=10)
        if response.status_code == 200:
            logger.info(f"Successfully deleted {file_name} from Google File API!")
        else:
            logger.warning(f"Google File API delete returned status {response.status_code}: {response.text}")
    except Exception as e:
        logger.warning(f"Failed to delete {file_name} from Google File API: {e}")


def get_sample_image_base64() -> str:
    """Load sample reference image as Base64 string from local file."""
    if os.path.exists(DEFAULT_SAMPLE_PATH):
        try:
            with open(DEFAULT_SAMPLE_PATH, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to load local sample image: {e}")
    return ""


def extract_codes_via_gemini_vision(stream_data: bytes | Image.Image = None, api_key: str = None) -> Tuple[List[str], List[str]]:
    """Extract small and large reward codes using Gemini 2.5 Flash Vision AI:
    - Image 1: Sample reference UI layout (Base64)
    - Image 2: Official Google File API uploaded stream screenshot URI (file_uri)
    - Auto-deletes screenshot from Google File API after extraction.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_API_KEY environment variable not provided.")
        return [], []

    file_name, file_uri = "", ""
    if stream_data:
        file_name, file_uri = upload_to_google_file_api(stream_data, key)

    if not file_uri:
        logger.error("Failed to obtain valid Google File API URI for screenshot.")
        return [], []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"

    sample_b64 = get_sample_image_base64()

    prompt = (
        "Image 1 is the reference sample UI layout showing where reward codes appear (yellow speech bubbles for small codes next to chests, and pink banner for large code). "
        "Image 2 (from Google File API URI) is the live stream screenshot. Compare Image 2 against Image 1 and extract: "
        "1) All small reward codes visible in the yellow speech bubbles. Preserve exact character casing (e.g. 'w3qg8mz5'). "
        "2) The large reward code in the pink banner if released. IMPORTANT: Large Codes in this game are ALWAYS 100% UPPERCASE letters and digits (e.g., 'HN9KJMEW', 'R5XJV9VQ2', 'K9X3P7WB'). Ensure all letters in large_codes are UPPERCASE. If the pink banner says 'Sắp xuất hiện' or is not released, do not include it in large_codes. "
        "\nCRITICAL OCR CHARACTER ACCURACY INSTRUCTIONS:\n"
        "- Inspect each character stroke with extreme precision to prevent confusing similar shapes:\n"
        "  * 'J' (curved bottom hook) vs 'I' (straight vertical line) / 'L' (right-angle base).\n"
        "  * 'E' (3 horizontal parallel bars) vs 'B' (2 closed rounded loops) / '8'.\n"
        "  * '0' (number zero) vs 'O' (uppercase letter O) vs 'o' (lowercase letter o).\n"
        "  * '1' (number one) vs 'I' (uppercase i) vs 'l' (lowercase L).\n"
        "  * '5' (number five) vs 'S' (uppercase S) vs 's' (lowercase s).\n"
        "  * '8' (number eight) vs 'B' (uppercase B).\n"
        "  * 'g' (lowercase g with descender) vs '9' (number nine) vs 'q'.\n"
        "  * 'u' (lowercase u) vs 'v' (lowercase v) vs 'U' / 'V'.\n"
        "  * 'w' (lowercase w) vs 'vv' (two v's) vs 'W' (uppercase W).\n"
        "- Return ONLY a valid JSON object with format: {\"small_codes\": [\"code1\", \"code2\"], \"large_codes\": [\"CODE3\"]}"
    )

    parts = [{"text": prompt}]

    # Attach Image 1: Sample reference image
    if sample_b64:
        parts.append({"inline_data": {"mime_type": "image/png", "data": sample_b64}})

    # Attach Image 2: Official Google File API URI
    parts.append({
        "file_data": {
            "file_uri": file_uri,
            "mime_type": "image/png"
        }
    })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json"
        }
    }

    headers = {"Content-Type": "application/json"}

    timeout_sec = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
    small_codes, large_codes = [], []
    try:
        for attempt in range(2):
            try:
                logger.info(f"Sending Gemini Vision API request (attempt {attempt+1}/2, timeout={timeout_sec}s)...")
                response = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                res_json = response.json()

                if "error" in res_json:
                    logger.error(f"Gemini API Error: {res_json['error']}")
                    break
                else:
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        logger.info(f"Gemini AI Raw Response: {content_text}")

                        parsed = json.loads(content_text)
                        small_codes = parsed.get("small_codes", [])
                        large_codes = parsed.get("large_codes", [])

                        small_codes = [s.strip() for s in small_codes if isinstance(s, str) and s.strip()]
                        # Large codes in this game are ALWAYS 100% UPPERCASE
                        large_codes = [l.strip().upper() for l in large_codes if isinstance(l, str) and l.strip()]
                        break

            except requests.exceptions.ReadTimeout:
                logger.warning(f"Gemini Vision API call timed out on attempt {attempt+1} (timeout={timeout_sec}s). Retrying...")
            except Exception as e:
                logger.error(f"Gemini Vision API call failed: {e}", exc_info=True)
                break
    finally:
        # Immediately delete temporary file from Google File API server after process
        if file_name:
            delete_from_google_file_api(file_name, key)

    return small_codes, large_codes
