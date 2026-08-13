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
    """Delete temporary uploaded screenshot files but never the configured sample reference image."""
    if not file_name:
        return

    sample_reference = (DEFAULT_SAMPLE_PATH or "").strip()
    if sample_reference:
        if file_name in sample_reference or sample_reference.endswith(file_name):
            logger.info(f"Skipping deletion of protected sample reference: {sample_reference}")
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
    """Convert Gemini [x1, y1, x2, y2] pixel coordinates to safe image coordinates."""
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None

    try:
        x1, y1, x2, y2 = [float(v) for v in box]
    except (TypeError, ValueError):
        return None

    if not all([
        0 <= x1 < width,
        0 <= x2 <= width,
        0 <= y1 < height,
        0 <= y2 <= height,
        x2 > x1,
        y2 > y1,
    ]):
        logger.warning(
            f"Invalid Gemini pixel box: {box}, "
            f"image_size={width}x{height}"
        )
        return None

    return [
        int(round(x1)),
        int(round(y1)),
        int(round(x2)),
        int(round(y2)),
    ]


def crop_combined_bounding_box(img_data: bytes | Image.Image, boxes: List[List[int]], padding_percent: float = 0.01) -> bytes | None:
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

    if isinstance(stream_data, Image.Image):
        live_img = stream_data.copy()
    else:
        live_img = Image.open(io.BytesIO(stream_data))
    live_width, live_height = live_img.size

    try:
        prompt = f"""
        You are performing precise visual localization on a screenshot.

        You are given TWO images.

        IMAGE 1 — LIVE SCREENSHOT:
        - This is the original full screenshot captured from the browser.
        - Original dimensions:
        WIDTH = {live_width}
        HEIGHT = {live_height}
        - All coordinates MUST refer to this original image.

        IMAGE 2 — REFERENCE IMAGE:
        - This is a cropped reference image of the reward panel.
        - The reference image has been resized/enlarged and may have a different scale from the corresponding region in IMAGE 1.
        - DO NOT assume that IMAGE 2 has the same pixel scale or dimensions as the target region in IMAGE 1.
        - Use IMAGE 2 only as a visual reference for identifying the target structure.

        TASK:

        Find the reward-panel region in IMAGE 1 that visually corresponds to IMAGE 2.

        The target reward panel is the complete reward UI area shown in the reference image.

        It contains:
        1. The vertical column of reward/chest icons on the left.
        2. The reward amount/bubble area.
        3. The large reward-code banner below the reward icons.
        4. The surrounding decorative/background area that belongs to the same reward panel.

        IMPORTANT MATCHING RULES:

        - The reward codes are DYNAMIC and may be different between screenshots.
        - DO NOT use the actual code characters as the primary matching feature.
        - Ignore differences in the code text.
        - Focus on stable visual elements:
        - reward/chest icons
        - icon positions
        - spacing
        - panel borders
        - shapes
        - decorative elements
        - background structure
        - relative positions of all elements
        - IMAGE 2 is a resized/enlarged crop.
        - You MUST account for the scale difference between IMAGE 1 and IMAGE 2.
        - DO NOT copy IMAGE 2's pixel dimensions into the result.
        - DO NOT assume a 1:1 pixel correspondence between the two images.

        COORDINATE SYSTEM:

        Use ONLY the original pixel coordinate system of IMAGE 1.

        The top-left pixel of IMAGE 1 is:

        (0, 0)

        X increases from left to right.
        Y increases from top to bottom.

        Return:

        [x1, y1, x2, y2]

        where:

        x1 = left edge of the complete reward panel
        y1 = top edge of the complete reward panel
        x2 = right edge of the complete reward panel
        y2 = bottom edge of the complete reward panel

        The bounding box must tightly contain the COMPLETE reward panel.

        Do NOT include:
        - TikTok chat
        - TikTok sidebar
        - video player controls
        - unrelated UI
        - large empty areas outside the reward panel

        Do NOT crop any part of the reward panel.

        VISUAL VERIFICATION:

        Before returning coordinates:

        1. Identify the reward-panel structure in IMAGE 2.
        2. Ignore IMAGE 2's absolute pixel dimensions.
        3. Find the same visual structure in IMAGE 1.
        4. Verify multiple independent landmarks:
        - reward/chest column
        - spacing between reward icons
        - reward bubble/banner
        - panel borders
        - decorative background
        - relative positions of these elements
        5. Determine the bounding box only after these landmarks match.
        6. Verify that all coordinates are inside IMAGE 1.

        Coordinate constraints:

        0 <= x1 < x2 <= {live_width}
        0 <= y1 < y2 <= {live_height}

        IMPORTANT:

        Do NOT return normalized coordinates.

        Do NOT use the 0-1000 coordinate system.

        Do NOT use coordinates relative to IMAGE 2.

        Do NOT use coordinates from a resized version of IMAGE 1.

        Use the ORIGINAL PIXEL COORDINATES of IMAGE 1.

        If the target reward panel cannot be identified with high confidence, DO NOT GUESS.

        Return:

        {{"ui_box_2d":[]}}

        OUTPUT FORMAT:

        Return ONLY a valid JSON object.

        If detected:

        {{"ui_box_2d":[x1,y1,x2,y2]}}

        If not confidently detected:

        {{"ui_box_2d":[]}}

        Do not return markdown.
        Do not return code fences.
        Do not return explanations.
        Do not return confidence scores.
        Do not return any additional fields.
        """

        parts = [{"text": prompt}]

        # IMAGE 1: LIVE screenshot
        parts.append({
            "file_data": {
                "file_uri": file_uri,
                "mime_type": "image/png"
            }
        })

        # IMAGE 2: Reference/sample image
        if sample_reference:
            parts.append({
                "file_data": {
                    "file_uri": sample_reference,
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
                        logger.info(
                            f"Gemini UI box: {ui_box} | "
                            f"original image size: {live_width}x{live_height}"
                        )
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

    logger.info(f"Cropping detected UI box: {ui_box}")
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
            "Use ONLY the visible image content as the source of truth. "
            "Do NOT use external knowledge, previous screenshots, sample images, or expected code patterns. "
            "\n\n"

            "TASK: "
            "Extract every currently visible reward code from the cropped reward panel. "
            "\n\n"

            "There are TWO types of reward codes: "
            "1. SMALL CODES: codes displayed inside the yellow reward bubbles. "
            "2. LARGE CODES: the code displayed inside the large pink banner at the bottom. "
            "\n\n"

            "IMPORTANT — CODE BOUNDARIES: "
            "Only read characters that are actually inside a valid reward-code area. "
            "Do NOT read surrounding UI text, labels, numbers, icons, usernames, counters, or decorative text. "
            "Do NOT combine characters from different bubbles into one code. "
            "Each yellow bubble represents one separate small code. "
            "The pink banner represents one large code. "
            "\n\n"

            "IMPORTANT — EXACT CHARACTER RECOGNITION: "
            "Read every code character strictly from LEFT TO RIGHT in its visual order. "
            "Never reorder, swap, reverse, or rearrange characters. "
            "The position of every character in the output must exactly match its position in the image. "
            "\n\n"

            "Inspect each character individually before producing the final result. "
            "Pay special attention to visually similar characters, including: "
            "'f' vs '1', "
            "'J' vs 'I' vs 'L', "
            "'E' vs 'B' vs '8', "
            "'0' vs 'O' vs 'o', "
            "'1' vs 'I' vs 'l' vs 'f', "
            "'5' vs 'S' vs 's', "
            "'8' vs 'B', "
            "'g' vs '9' vs 'q', "
            "'u' vs 'v' vs 'U' vs 'V', "
            "'w' vs 'vv' vs 'W'. "
            "\n\n"

            "Do NOT automatically normalize ambiguous characters. "
            "If the image clearly shows lowercase, preserve lowercase. "
            "If the image clearly shows uppercase, preserve uppercase. "
            "If the image clearly shows a digit, preserve the digit. "
            "\n\n"

            "SMALL CODE RULES: "
            "Small codes may contain lowercase letters, uppercase letters, and digits. "
            "Preserve the exact visible casing. "
            "Do not convert lowercase to uppercase. "
            "Do not convert uppercase to lowercase. "
            "Do not replace letters with digits or digits with letters unless the visual character itself clearly indicates that character. "
            "\n\n"

            "LARGE CODE RULES: "
            "The large code in the pink banner is uppercase when visible. "
            "Return the characters exactly in their visible left-to-right order. "
            "Do not include the surrounding banner text. "
            "\n\n"

            "CRITICAL — DO NOT GUESS: "
            "If a character is partially obscured, blurred, cut off, distorted, or genuinely ambiguous, "
            "do NOT invent a character based on what the code is expected to be. "
            "Use the visible character only. "
            "If an entire code cannot be reliably read, do not fabricate a complete code. "
            "\n\n"

            "CRITICAL — VISUAL VERIFICATION: "
            "Before returning each code, perform a second visual pass over the image. "
            "For every code: "
            "1. Identify its exact boundaries. "
            "2. Count the visible characters. "
            "3. Read them from left to right. "
            "4. Compare each character against the image again. "
            "5. Verify that no character was skipped, duplicated, swapped, or invented. "
            "\n\n"

            "If the same code appears more than once in the image, return it only once. "
            "Do not invent missing codes. "
            "Do not use sample/reference text as a fallback. "
            "Do not infer a code from previous runs. "
            "\n\n"

            "OUTPUT FORMAT: "
            "Return ONLY valid JSON using exactly this schema: "
            "{\"small_codes\": [], \"large_codes\": []}. "
            "Do not return markdown. "
            "Do not return explanations. "
            "Do not return confidence scores. "
            "Do not return additional fields. "
            "Do not include any text outside the JSON object."
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
