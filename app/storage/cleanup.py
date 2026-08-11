import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_old_daily_files(data_dir: str | Path = "data", retention_days: int = 7) -> int:
    """Delete daily code txt files older than retention_days (defaults to 7 days)."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return 0

    today = datetime.now().date()
    today_filename = f"{today.strftime('%Y-%m-%d')}.txt"
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
