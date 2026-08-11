import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_old_daily_files(data_directory: str | Path = "data", today_str: Optional[str] = None) -> int:
    """Delete all previous daily txt files in data_directory except today's file."""
    data_dir = Path(data_directory)
    if not data_dir.exists():
        return 0

    if not today_str:
        today_str = datetime.now().strftime("%Y-%m-%d")

    today_filename = f"{today_str}.txt"
    deleted_count = 0

    for file_path in data_dir.glob("*.txt"):
        if file_path.name != today_filename:
            try:
                file_path.unlink()
                deleted_count += 1
                logger.info(f"Cleaned up previous day code file: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to delete old file {file_path.name}: {e}")

    return deleted_count


def cleanup_temp_screenshots(screenshots_dir: str | Path = "screenshots", debug_dir: str | Path = "debug") -> int:
    """Delete temporary screenshots and debug crops to keep local directory clean."""
    deleted_count = 0

    for target in [Path(screenshots_dir), Path(debug_dir)]:
        if target.exists():
            for img in target.glob("*.png"):
                try:
                    img.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Could not remove temp image {img.name}: {e}")

    logger.info(f"Cleaned up {deleted_count} temporary screenshot images.")
    return deleted_count
