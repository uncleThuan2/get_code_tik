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

# Blacklisted substrings derived from OCRing non-live profile page or UI text
BLACKLISTED_SUBSTRINGS = [
    "HOAVIEN",
    "GIDIHOA",
    "THEGIOI",
    "CUATOI",
    "INTERNET",
    "5000P",
    "3000P",
    "1500P",
    "500P",
    "VIENCU",
    "IDIHOA",
    "PESTNN",
    "HEGIDI",
    "NEGIDI",
    "HGIDI",
    "GIDI",
]


def clean_ocr_text(text: str) -> str:
    """Normalize raw OCR text by removing spaces, punctuation, and newlines while preserving letter casing."""
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", text)


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

    # Reject blacklisted UI substrings
    cleaned_upper = cleaned.upper()
    for bad in BLACKLISTED_SUBSTRINGS:
        if bad in cleaned_upper:
            return False

    # Reward codes in this game must contain both letters and digits
    if not re.search(r"[A-Za-z]", cleaned) or not re.search(r"\d", cleaned):
        return False

    # Digits must not dominate the candidate code (> 60% digits is UI point noise like 115000V)
    digit_count = sum(1 for c in cleaned if c.isdigit())
    if (digit_count / len(cleaned)) > 0.60:
        return False

    return True
