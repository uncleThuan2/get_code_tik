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

DEFAULT_SAMPLE_PATH = os.getenv("DEFAULT_SAMPLE_PATH") or os.getenv("SAMPLE_REFERENCE_IMAGE_PATH", "")


def _get_gemini_model_candidates() -> List[str]:
    """Return the preferred Gemini model plus safe fallbacks when a model is overloaded."""
    configured = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    candidates = [configured] if configured else []
    fallback_models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-preview-05-06",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]

    for model in fallback_models:
        if model not in candidates:
            candidates.append(model)

    return candidates


def _is_model_not_available_error(res_json: dict) -> bool:
    """Detect model names that Google disabled for new users or removed from service."""
    if not isinstance(res_json, dict):
        return False

    error = res_json.get("error", {})
    if not isinstance(error, dict):
        return False

    status = str(error.get("status", "")).upper()
    message = str(error.get("message", "")).lower()

    return status == "NOT_FOUND" and "no longer available" in message


def _is_transient_gemini_error(res_json: dict) -> bool:
    """Google AI can return 503/429/RESOURCE_EXHAUSTED while a model is busy; these are retryable."""
    if not isinstance(res_json, dict):
        return False

    error = res_json.get("error", {})
    if isinstance(error, dict):
        code = error.get("code")
        status = str(error.get("status", "")).upper()
        message = str(error.get("message", "")).lower()

        if _is_model_not_available_error(res_json):
            return False

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


def _normalize_box_to_pixels(box: List[int], width: int, height: int):
    """Normalize Gemini box values into pixel coordinates, supporting both 0..1000 and raw pixel formats."""
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None

    try:
        vals = [float(v) for v in box]
    except (TypeError, ValueError):
        return None

    if any(not (0 <= v <= 10000) for v in vals):
        return None

    ymin, xmin, ymax, xmax = vals

    # Gemini often returns normalized [ymin, xmin, ymax, xmax] in 0..1000.
    if max(vals) <= 1000:
        xmin = xmin / 1000.0 * width
        ymin = ymin / 1000.0 * height
        xmax = xmax / 1000.0 * width
        ymax = ymax / 1000.0 * height

    x1 = max(0, min(width, xmin))
    y1 = max(0, min(height, ymin))
    x2 = max(0, min(width, xmax))
    y2 = max(0, min(height, ymax))

    if x2 <= x1 or y2 <= y1:
        return None

    return [int(x1), int(y1), int(x2), int(y2)]


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
        normalized_boxes = []
        for box in valid_boxes:
            normalized = _normalize_box_to_pixels(box, width, height)
            if normalized is not None:
                normalized_boxes.append(normalized)

        if not normalized_boxes:
            return None

        min_x1 = min(b[0] for b in normalized_boxes)
        min_y1 = min(b[1] for b in normalized_boxes)
        max_x2 = max(b[2] for b in normalized_boxes)
        max_y2 = max(b[3] for b in normalized_boxes)

        pad_y = max(1, int(height * padding_percent))
        pad_x = max(1, int(width * padding_percent))

        left = max(0, min_x1 - pad_x)
        top = max(0, min_y1 - pad_y)
        right = min(width, max_x2 + pad_x)
        bottom = min(height, max_y2 + pad_y)

        if right <= left or bottom <= top:
            return None

        cropped = img.crop((left, top, right, bottom))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Failed to crop combined bounding box: {e}")
        return None


def detect_ui_box_via_gemini_vision(stream_data: bytes | Image.Image, api_key: str, sample_reference: str = "") -> List[int]:
    """Step 1: identify the UI crop box from the live screenshot against the sample reference."""
    if not stream_data:
        return []

    file_name, file_uri = upload_to_google_file_api(stream_data, api_key)
    if not file_uri:
        logger.error("Failed to obtain valid Google File API URI for screenshot detection step.")
        return []

    try:
        prompt = (
            "Compare the reference sample and the live screenshot. "
            "Find the single reward-panel area in the live screenshot that matches the reference layout. "
            "Return ONLY a JSON object in this exact format: {\"ui_box_2d\": [x1, y1, x2, y2]} using the image's actual pixel coordinates, not normalized 0..1000 values. "
            "Use the real screenshot size: x and y are pixel positions in the full image. "
            "The box should tightly cover the full reward-panel region, including the left chest column, reward bubble area, and the large reward banner. "
            "Do not guess; if the match is unclear, return {\"ui_box_2d\": []}."
        )

        parts = [{"text": prompt}]
        if sample_reference:
            parts.append({"file_data": {"file_uri": sample_reference, "mime_type": "image/png"}})
        parts.append({"file_data": {"file_uri": file_uri, "mime_type": "image/png"}})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        }

        timeout_sec = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
        max_attempts = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        backoff_seconds = int(os.getenv("GEMINI_BACKOFF_SECONDS", "2"))
        model_candidates = _get_gemini_model_candidates()

        for attempt in range(max_attempts):
            for model_name in model_candidates:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=timeout_sec)
                    res_json = response.json()

                    if "error" in res_json:
                        if _is_model_not_available_error(res_json):
                            logger.warning(f"Model {model_name} is no longer available; trying next fallback model...")
                            continue
                        if _is_transient_gemini_error(res_json):
                            logger.warning(f"Transient Gemini error during UI detection; retrying in {backoff_seconds}s...")
                            time.sleep(backoff_seconds)
                            continue
                        logger.error(f"Gemini UI detection error: {res_json}")
                        break

                    candidates = res_json.get("candidates", [])
                    if candidates:
                        content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        parsed = json.loads(content_text)
                        ui_box = parsed.get("ui_box_2d")
                        if isinstance(ui_box, list) and len(ui_box) == 4:
                            return [int(float(v)) for v in ui_box]
                        return []

                    logger.warning(f"Gemini detection step returned no candidates for model={model_name}.")
                except requests.exceptions.ReadTimeout:
                    logger.warning(f"Gemini detection timeout for model={model_name}; retrying...")
                    time.sleep(backoff_seconds)
                    continue
                except Exception as e:
                    logger.error(f"Gemini detection request failed for model={model_name}: {e}", exc_info=True)
                    break

            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))

        return []
    finally:
        if file_name:
            delete_from_google_file_api(file_name, api_key)


def extract_codes_via_gemini_vision(stream_data: bytes | Image.Image = None, api_key: str = None) -> Tuple[List[str], List[str], bytes | None]:
    """Two-stage OCR flow:
    1) detect area box from the full screenshot,
    2) crop that area and OCR the crop image using a second prompt.
    Returns:
        (small_codes: List[str], large_codes: List[str], sample_cropped_bytes: bytes | None)
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        logger.warning("GEMINI_API_KEY environment variable not provided.")
        return [], [], None

    if not stream_data:
        return [], [], None

    sample_reference = (DEFAULT_SAMPLE_PATH or "").strip()

    ui_box = detect_ui_box_via_gemini_vision(stream_data, key, sample_reference)
    if not ui_box:
        logger.warning("No valid UI box detected from screenshot. Returning empty code list.")
        return [], [], None

    sample_cropped_bytes = crop_combined_bounding_box(stream_data, [ui_box])
    if not sample_cropped_bytes:
        logger.warning("Failed to crop screenshot with detected box. Returning empty code list.")
        return [], [], None

    crop_file_name, crop_file_uri = upload_to_google_file_api(sample_cropped_bytes, key)
    if not crop_file_uri:
        logger.error("Failed to upload cropped image to Google File API for OCR step.")
        return [], [], sample_cropped_bytes

    try:
        prompt = (
            "You are given exactly ONE image only: the cropped reward-panel image. "
            "Use the image content itself as the source of truth. "
            "Read only the reward codes inside the valid panel area: yellow small-code bubbles, and the large pink banner at the bottom. "
            "Preserve exact letter casing for small codes and uppercase for large codes. "        
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
            "- A small code can contain lowercase and digits, but only read what is actually visible.\n"
            "- The large banner code is always uppercase if it is visible.\n"
            "Return ONLY valid JSON in this exact schema: {\"small_codes\": [], \"large_codes\": []}. "
            "Do not invent values, do not use sample text as fallback, and do not include any extra text outside JSON."
        )

        parts = [{"text": prompt}]
        parts.append({"file_data": {"file_uri": crop_file_uri, "mime_type": "image/png"}})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        }

        timeout_sec = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
        max_attempts = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        backoff_seconds = int(os.getenv("GEMINI_BACKOFF_SECONDS", "2"))
        model_candidates = _get_gemini_model_candidates()

        for attempt in range(max_attempts):
            for model_name in model_candidates:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                    logger.info(f"Sending cropped OCR request (attempt {attempt + 1}/{max_attempts}, model={model_name})...")
                    response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=timeout_sec)
                    res_json = response.json()

                    if "error" in res_json:
                        if _is_model_not_available_error(res_json):
                            logger.warning(f"Model {model_name} is no longer available; trying next fallback model...")
                            continue
                        if _is_transient_gemini_error(res_json):
                            logger.warning(f"Transient Gemini error during OCR; retrying in {backoff_seconds}s...")
                            time.sleep(backoff_seconds)
                            continue
                        logger.error(f"Gemini OCR error: {res_json}")
                        break

                    candidates = res_json.get("candidates", [])
                    if candidates:
                        content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        logger.info(f"Gemini cropped OCR raw response: {content_text}")
                        parsed = json.loads(content_text)
                        raw_small = parsed.get("small_codes", [])
                        raw_large = parsed.get("large_codes", [])
                        small_codes = [s.strip() for s in raw_small if isinstance(s, str) and s.strip()]
                        large_codes = [l.strip().upper() for l in raw_large if isinstance(l, str) and l.strip()]
                        return small_codes, large_codes, sample_cropped_bytes

                    logger.warning(f"Gemini OCR step returned no candidates for model={model_name}.")
                except requests.exceptions.ReadTimeout:
                    logger.warning(f"Gemini OCR timeout for model={model_name}; retrying...")
                    time.sleep(backoff_seconds)
                    continue
                except Exception as e:
                    logger.error(f"Gemini OCR request failed for model={model_name}: {e}", exc_info=True)
                    break

            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds * (attempt + 1))

        return [], [], sample_cropped_bytes
    finally:
        if crop_file_name:
            delete_from_google_file_api(crop_file_name, key)
