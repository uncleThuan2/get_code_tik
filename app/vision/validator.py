import re
from typing import Optional

# Generic reward code regex: 6 to 16 alphanumeric characters
CODE_REGEX = re.compile(r"^[A-Za-z0-9]{6,16}$")

# Phrases indicating code has not been released yet or UI noise
NOT_RELEASED_KEYWORDS = [
    "GIỚI HẠN",
    "GIOI HAN",
    "CODE GIỚI HẠN",
    "CODE GIOI HAN",
    "CODE TIẾP THEO",
    "CODE TIEP THEO",
    "HIỆU LỰC",
    "HIEU LUC",
    "TIPS CHỦ VƯỜN",
    "SÁNG TẠO",
    "PHÚT",
    "PHUT",
    "TẢI GAME",
    "TAI GAME",
    "ĐẶC QUYỀN",
    "DAC QUYEN",
    "HOÀN THÀNH",
    "HOAN THANH",
    "HOA VIÊN",
    "HOA VIEN",
    "THẾ GIỚI",
    "THE GIOI",
    "CHÀO MỪNG",
    "CHAO MUNG",
]


def clean_ocr_text(text: str) -> str:
    """Normalize raw OCR text by removing spaces, punctuation, and newlines."""
    if not text:
        return ""
    # Strip whitespace and non-alphanumeric characters
    cleaned = re.sub(r"[^A-Za-z0-9]", "", text)
    return cleaned.upper()


def is_not_released(raw_text: str) -> bool:
    """Check if OCR text matches placeholder phrases indicating code is not released."""
    if not raw_text:
        return False
    upper_text = raw_text.upper()
    for kw in NOT_RELEASED_KEYWORDS:
        if kw in upper_text:
            return True
    return False


def is_valid_code(candidate: str) -> bool:
    """Validate candidate code against format rules and blacklist patterns."""
    if not candidate:
        return False

    cleaned = clean_ocr_text(candidate)

    # Reject if too short or too long
    if len(cleaned) < 6 or len(cleaned) > 16:
        return False

    # Check regex pattern
    if not CODE_REGEX.match(cleaned):
        return False

    # Reject known UI text patterns
    if is_not_released(candidate):
        return False

    return True
