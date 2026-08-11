import logging
from typing import Optional, List, Tuple
from PIL import Image

from app.vision.preprocess import preprocess_image_variants
from app.vision.validator import clean_ocr_text, is_valid_code, is_not_released

logger = logging.getLogger(__name__)


def extract_code_from_crop(crop_img: Image.Image, psm_mode: int = 7) -> Tuple[Optional[str], bool]:
    """Perform OCR on crop image across multiple preprocessed variants.

    Returns:
        (extracted_code: Optional[str], is_not_released_flag: bool)
    """
    try:
        import pytesseract
    except ImportError:
        logger.error("pytesseract is not installed in Python environment.")
        return None, False

    variants = preprocess_image_variants(crop_img)

    for idx, variant in enumerate(variants):
        try:
            # PSM 7: Treat the image as a single text line
            # PSM 6: Assume a single uniform block of text
            for psm in [psm_mode, 6, 3]:
                config_str = f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                raw_text = pytesseract.image_to_string(variant, config=config_str).strip()

                if is_not_released(raw_text):
                    logger.debug(f"OCR Variant {idx} (PSM {psm}) detected placeholder: '{raw_text}'")
                    return None, True

                cleaned = clean_ocr_text(raw_text)
                if is_valid_code(cleaned):
                    logger.info(f"OCR Success (Variant {idx}, PSM {psm}): Found valid code -> '{cleaned}'")
                    return cleaned, False

        except Exception as e:
            logger.debug(f"OCR error on variant {idx}: {e}")
            continue

    return None, False
