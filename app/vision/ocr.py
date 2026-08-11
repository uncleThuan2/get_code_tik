import logging
from typing import Optional, List, Tuple
from PIL import Image

from app.vision.preprocess import preprocess_image_variants
from app.vision.validator import clean_ocr_text, is_valid_code, is_not_released

logger = logging.getLogger(__name__)


def extract_codes_from_crop(crop_img: Image.Image) -> Tuple[List[str], bool]:
    """Perform OCR on cropped region across preprocessed variants to extract ALL valid codes (supporting multi-line small code stacks).

    Returns:
        (extracted_codes: List[str], is_not_released_flag: bool)
    """
    try:
        import pytesseract
    except ImportError:
        logger.error("pytesseract is not installed in Python environment.")
        return [], False

    variants = preprocess_image_variants(crop_img)
    found_codes: List[str] = []
    not_released = False

    for idx, variant in enumerate(variants):
        try:
            # Use PSM 6 (uniform block) and PSM 7 (single line) only
            # Avoid PSM 11 (sparse text) and PSM 3 which stitch random noise
            for psm in [6, 7]:
                config_str = f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                raw_text = pytesseract.image_to_string(variant, config=config_str).strip()

                if is_not_released(raw_text):
                    not_released = True

                lines = raw_text.splitlines()
                for line in lines:
                    cleaned = clean_ocr_text(line)
                    if is_valid_code(cleaned) and cleaned not in found_codes:
                        logger.info(f"OCR Success (Variant {idx}, PSM {psm}): Found valid code -> '{cleaned}'")
                        found_codes.append(cleaned)

        except Exception as e:
            logger.debug(f"OCR error on variant {idx}: {e}")
            continue

    return found_codes, not_released


def extract_code_from_crop(crop_img: Image.Image, psm_mode: int = 7) -> Tuple[Optional[str], bool]:
    """Single code extraction backward-compatible wrapper."""
    codes, not_released = extract_codes_from_crop(crop_img)
    first_code = codes[0] if codes else None
    return first_code, not_released
