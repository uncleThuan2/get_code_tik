import logging
from pathlib import Path
from typing import Set, List

from app.storage.daily_file import read_daily_codes

logger = logging.getLogger(__name__)


def is_duplicate_code(code: str, data_dir: str | Path = "data") -> bool:
    """Check if code already exists in today's daily file (case-insensitive duplicate check)."""
    if not code:
        return True

    existing_codes = read_daily_codes(data_dir=data_dir)
    existing_upper = {c.upper() for c in existing_codes}
    is_dup = code.upper() in existing_upper
    if is_dup:
        logger.info(f"Duplicate code detected (already saved today): '{code}'")
    return is_dup


def filter_new_codes(candidate_codes: List[str], data_dir: str | Path = "data") -> List[str]:
    """Filter list of candidate codes, returning only genuinely new codes while preserving exact original letter casing."""
    existing = read_daily_codes(data_dir=data_dir)
    existing_upper = {c.upper() for c in existing}
    new_codes = []
    seen_upper = set()

    for code in candidate_codes:
        if code and code.strip():
            raw_code = code.strip()
            code_up = raw_code.upper()
            if code_up not in existing_upper and code_up not in seen_upper:
                new_codes.append(raw_code)
                seen_upper.add(code_up)

    return new_codes
