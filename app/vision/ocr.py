import os
import logging
from typing import List, Tuple
from PIL import Image

from app.vision.gemini_ocr import extract_codes_via_gemini_vision

logger = logging.getLogger(__name__)


def extract_all_codes_from_stream(stream_data: bytes | Image.Image) -> Tuple[List[str], List[str], bytes | None]:
    """Extract small and large reward codes directly from stream screenshot bytes using Gemini 2.5 Flash Vision AI.

    Returns:
        (small_codes: List[str], large_codes: List[str], sample_cropped_bytes: bytes | None)
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        logger.error("GEMINI_API_KEY environment variable is missing!")
        return [], [], None

    logger.info("Extracting reward codes via Gemini 2.5 Flash Vision AI (In-Memory Stream Bytes)...")
    return extract_codes_via_gemini_vision(stream_data, api_key=gemini_key)
