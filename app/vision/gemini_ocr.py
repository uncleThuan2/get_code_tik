import os
import io
import json
import base64
import time
import requests
import logging
from typing import Tuple, List
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_PATH = "sample/co_code_lon.png"


def _get_gemini_model_candidates() -> List[str]:
    """Return the preferred Gemini model plus safe fallbacks when a model is overloaded."""
    configured = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    candidates = [configured] if configured else []
    fallback_models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ]

    for model in fallback_models:
        if model not in candidates:
            candidates.append(model)

    return candidates


def _is_transient_gemini_error(res_json: dict) -> bool:
    """Google AI can return 503/429/RESOURCE_EXHAUSTED while a model is busy; these are retryable."""
    if not isinstance(res_json, dict):
        return False

    error = res_json.get("error", {})
    if isinstance(error, dict):
        code = error.get("code")
        status = str(error.get("status", "")).upper()
        message = str(error.get("message", "")).lower()

        if code in (429, 503) or status in {"UNAVAILABLE", "RESOURCE_EXHAUSTED", "RATE_LIMIT_EXCEEDED", "DEADLINE_EXCEEDED"}:
            return True

        if any(token in message for token in [
            "high demand",
            "overloaded",
            "temporarily unavailable",
            "rate limit",
            "exhausted",
            "busy"
        ]):
            return True

    return False


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
            file_name = file_info.get("name", "")
            file_uri = file_info.get("uri", "")
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


def crop_combined_bounding_box(img_data: bytes | Image.Image, boxes: List[List[int]], padding_percent: float = 0.04) -> bytes | None:
    """Crop 1 SINGLE combined image region covering ALL detected code regions (matching sample layout region)."""
    valid_boxes = [b for b in boxes if isinstance(b, list) and len(b) == 4]
    if not img_data or not valid_boxes:
        return None

    try:
        if isinstance(img_data, Image.Image):
            img = img_data.copy()
        else:
            img = Image.open(io.BytesIO(img_data))

        width, height = img.size

        # Find 1 single bounding box that encompasses ALL codes
        min_ymin = min(b[0] for b in valid_boxes)
        min_xmin = min(b[1] for b in valid_boxes)
        max_ymax = max(b[2] for b in valid_boxes)
        max_xmax = max(b[3] for b in valid_boxes)

        # Add padding around the combined bounding box
        pad_y = int(height * padding_percent)
        pad_x = int(width * padding_percent)

        left = max(0, int((min_xmin / 1000.0) * width) - pad_x)
        top = max(0, int((min_ymin / 1000.0) * height) - pad_y)
        right = min(width, int((max_xmax / 1000.0) * width) + pad_x)
        bottom = min(height, int((max_ymax / 1000.0) * height) + pad_y)

        cropped = img.crop((left, top, right, bottom))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Failed to crop combined bounding box: {e}")
        return None


def extract_codes_via_gemini_vision(stream_data: bytes | Image.Image = None, api_key: str = None) -> Tuple[List[str], List[str], bytes | None]:
    """Extract small and large reward codes with bounding boxes, returning 1 single cropped sample image region:
    Returns:
        (small_codes: List[str], large_codes: List[str], sample_cropped_bytes: bytes | None)
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_API_KEY environment variable not provided.")
        return [], [], None

    file_name, file_uri = "", ""
    if stream_data:
        file_name, file_uri = upload_to_google_file_api(stream_data, key)

    if not file_uri:
        logger.error("Failed to obtain valid Google File API URI for screenshot.")
        return [], [], None

    sample_b64 = get_sample_image_base64()

    prompt = (
        "Image 1 is the reference sample UI layout showing the entire reward panel area (containing vertical chest progress column on the left, yellow speech bubbles for small codes, and the bottom pink banner for large code). "
        "Image 2 (from Google File API URI) is the live stream screenshot. Compare Image 2 against Image 1 and perform two tasks:\n"
        "1) Identify the 1 single overall bounding box [ymin, xmin, ymax, xmax] (normalized 0-1000 scale) on Image 2 that covers the ENTIRE UI panel area exactly matching Image 1's sample layout.\n"
        "2) Extract all reward codes visible inside that UI area:\n"
        "   - All small reward codes in yellow speech bubbles (preserve exact letter casing, e.g. 'w3qg8mz5').\n"
        "   - The large reward code in the pink banner if released (ALWAYS 100% UPPERCASE, e.g. 'HN9KJMEW').\n"
        "\nCRITICAL OCR CHARACTER ACCURACY & SEQUENCING INSTRUCTIONS:\n"
        "- STRICT LEFT-TO-RIGHT ORDERING: Read characters STRICTLY from LEFT to RIGHT in exact sequence. NEVER scramble or swap adjacent characters.\n"
        "- Inspect each character stroke with extreme precision to prevent confusing similar shapes:\n"
        "  * 'f' (lowercase f with top curve and crossbar) vs '1' (number one with straight top serif).\n"
        "  * 'J' (curved bottom hook) vs 'I' (straight vertical line) / 'L' (right-angle base).\n"
        "  * 'E' (3 horizontal parallel bars) vs 'B' (2 closed rounded loops) / '8'.\n"
        "  * '0' (zero) vs 'O' (uppercase O) vs 'o' (lowercase o).\n"
        "  * '1' (one) vs 'I' (uppercase i) vs 'l' (lowercase L) vs 'f' (lowercase f).\n"
        "  * '5' (five) vs 'S' (uppercase S) vs 's' (lowercase s).\n"
        "  * '8' (eight) vs 'B' (uppercase B).\n"
        "  * 'g' (lowercase g with descender) vs '9' (nine) vs 'q'.\n"
        "  * 'u' (lowercase u) vs 'v' (lowercase v) vs 'U' / 'V'.\n"
        "  * 'w' (lowercase w) vs 'vv' (two v's) vs 'W' (uppercase W).\n"
        "- Return ONLY a valid JSON object with this exact schema. DO NOT invent values from the sample template. If nothing is found, return empty lists, not sample strings. Example:\n"
        "{\n"
        "  \"ui_box_2d\": [],\n"
        "  \"small_codes\": [],\n"
        "  \"large_codes\": []\n"
        "}\n"
        "- If a real match is found, replace the empty arrays with actual values and use a valid box as [ymin, xmin, ymax, xmax]."
    )

    parts = [{"text": prompt}]

    if sample_b64:
        parts.append({"inline_data": {"mime_type": "image/png", "data": sample_b64}})

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
    max_attempts = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    backoff_seconds = int(os.getenv("GEMINI_BACKOFF_SECONDS", "2"))
    small_codes, large_codes = [], []
    sample_cropped_bytes = None
    model_candidates = _get_gemini_model_candidates()

    try:
        for attempt in range(max_attempts):
            last_error = None
            for model_name in model_candidates:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                    logger.info(f"Sending Gemini Vision API request (attempt {attempt + 1}/{max_attempts}, model={model_name}, timeout={timeout_sec}s)...")
                    response = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                    res_json = response.json()

                    if "error" in res_json:
                        last_error = res_json["error"]
                        logger.error(f"Gemini API Error for model={model_name}: {last_error}")
                        if _is_transient_gemini_error(res_json):
                            logger.warning(f"Transient Gemini error detected; retrying with backoff ({backoff_seconds}s)...")
                            time.sleep(backoff_seconds)
                            continue
                        break

                    candidates = res_json.get("candidates", [])
                    if candidates:
                        content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        logger.info(f"Gemini AI Raw Response: {content_text}")

                        parsed = json.loads(content_text)
                        ui_box = parsed.get("ui_box_2d")
                        raw_small = parsed.get("small_codes", [])
                        raw_large = parsed.get("large_codes", [])

                        small_codes = [s.strip() for s in raw_small if isinstance(s, str) and s.strip()]
                        large_codes = [l.strip().upper() for l in raw_large if isinstance(l, str) and l.strip()]

                        if stream_data and ui_box and isinstance(ui_box, list) and len(ui_box) == 4:
                            sample_cropped_bytes = crop_combined_bounding_box(stream_data, [ui_box])

                        return small_codes, large_codes, sample_cropped_bytes

                    logger.warning(f"Gemini returned no candidates for model={model_name}; trying next available model.")
                    break

                except requests.exceptions.ReadTimeout:
                    logger.warning(f"Gemini Vision API call timed out on model={model_name} (attempt {attempt + 1}/{max_attempts}). Retrying...")
                    time.sleep(backoff_seconds)
                    continue
                except Exception as e:
                    logger.error(f"Gemini Vision API call failed for model={model_name}: {e}", exc_info=True)
                    last_error = str(e)
                    break

            if last_error is not None and not _is_transient_gemini_error({"error": last_error}):
                break

            if attempt < max_attempts - 1:
                logger.info(f"Retrying Gemini request after transient failure (attempt {attempt + 2}/{max_attempts})...")
                time.sleep(backoff_seconds * (attempt + 1))

    finally:
        if file_name:
            delete_from_google_file_api(file_name, key)

    return small_codes, large_codes, sample_cropped_bytes
