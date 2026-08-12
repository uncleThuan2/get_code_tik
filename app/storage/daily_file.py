import logging
from datetime import datetime
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)


def get_daily_filepath(data_dir: str | Path = "data", date_str: str = None) -> Path:
    """Get path to today's data file (data/YYYY-MM-DD.txt)."""
    target_dir = Path(data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return target_dir / f"{date_str}.txt"


def read_daily_codes(data_dir: str | Path = "data", date_str: str = None) -> Set[str]:
    """Read and return all existing reward codes from today's daily file."""
    filepath = get_daily_filepath(data_dir, date_str)
    codes: Set[str] = set()

    if not filepath.exists():
        return codes

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("===") and not line.endswith(":"):
                    if line.upper() not in ("NOT_FOUND", "NOT_RELEASED"):
                        codes.add(line.upper())
    except Exception as e:
        logger.error(f"Error reading daily file {filepath}: {e}")

    return codes


def append_codes_to_daily_file(
    time_label: str,
    small_codes: List[str] = None,
    large_codes: List[str] = None,
    data_dir: str | Path = "data",
) -> Path:
    """Atomic write/append new reward codes entry to daily file."""
    filepath = get_daily_filepath(data_dir)
    small_codes = small_codes or []
    large_codes = large_codes or []

    content_lines = [f"\n=== {time_label} ===\n"]

    content_lines.append("Small Code:")
    if small_codes:
        for item in small_codes:
            code_str = item.get("code", "") if isinstance(item, dict) else str(item)
            content_lines.append(code_str)
    else:
        content_lines.append("NOT_FOUND")

    content_lines.append("\nLarge Code:")
    if large_codes:
        for item in large_codes:
            code_str = item.get("code", "") if isinstance(item, dict) else str(item)
            content_lines.append(code_str)
    else:
        content_lines.append("NOT_FOUND")

    content_lines.append("\n")
    entry_text = "\n".join(content_lines)

    # Read existing content if any
    existing_content = ""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            existing_content = f.read()

    new_content = existing_content + entry_text

    # Atomic write pattern
    temp_filepath = filepath.with_suffix(".tmp")
    with open(temp_filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
        f.flush()

    temp_filepath.replace(filepath)
    logger.info(f"Updated daily file: {filepath.resolve()}")
    return filepath
