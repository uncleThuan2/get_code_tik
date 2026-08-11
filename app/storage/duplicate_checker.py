import logging
from pathlib import Path
from typing import Set, List

from app.storage.daily_file import read_daily_codes

logger = logging.getLogger(__name__)


def is_duplicate_code(code: str, data_dir: str | Path = "data") -> bool:
    """Check if code already exists in today's daily file."""
    if not code:
        return True

    existing_codes = read_daily_codes(data_dir=data_dir)
    is_dup = code.upper() in existing_codes
    if is_dup:
        logger.info(f"Duplicate code detected (already saved today): '{code}'")
    return is_dup


def filter_new_codes(candidate_codes: List[str], data_dir: str | Path = "data") -> List[str]:
    """Filter list of candidate codes, returning only genuinely new codes."""
    existing = read_daily_codes(data_dir=data_dir)
    new_codes = []

    for code in candidate_codes:
        if code and code.upper() not in existing and code.upper() not in new_codes:
            new_codes.append(code.upper())

    return new_codes
