import asyncio
import logging
from typing import Optional, Tuple
from playwright.async_api import Page

from app.tiktok.profile import open_profile, is_profile_live, extract_live_url

logger = logging.getLogger(__name__)


async def detect_live_session(
    page: Page,
    profile_url: str,
    check_interval_seconds: int = 10,
    max_wait_minutes: int = 5,
    page_load_timeout: int = 30,
) -> Tuple[bool, Optional[str]]:
    """Poll profile page every check_interval_seconds up to max_wait_minutes for LIVE status.

    Returns:
        (is_live: bool, live_url: Optional[str])
    """
    max_attempts = max(1, (max_wait_minutes * 60) // check_interval_seconds)
    logger.info(f"Starting LIVE detection for {profile_url} (Max wait: {max_wait_minutes}m, Interval: {check_interval_seconds}s)")

    for attempt in range(1, max_attempts + 1):
        logger.info(f"LIVE detection check attempt {attempt}/{max_attempts}...")
        try:
            await open_profile(page, profile_url, timeout_seconds=page_load_timeout)
            live_status = await is_profile_live(page, profile_url)

            if live_status:
                live_url = await extract_live_url(page, profile_url)
                logger.info(f"LIVE detected on attempt {attempt}! LIVE URL: {live_url}")
                return True, live_url
            else:
                logger.info(f"Attempt {attempt}/{max_attempts}: Account is currently NOT LIVE.")

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_attempts} encountered error opening profile: {e}")

        if attempt < max_attempts:
            logger.info(f"Waiting {check_interval_seconds} seconds before retrying...")
            await asyncio.sleep(check_interval_seconds)

    logger.warning(f"No LIVE stream detected after {max_wait_minutes} minutes.")
    return False, None
