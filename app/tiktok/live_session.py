import asyncio
import logging
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def enter_and_capture_live_session(
    page: Page,
    live_url: str,
    output_screenshot_path: str | Path = "screenshots/live-screenshot.png",
    page_load_timeout: int = 30,
    render_delay_seconds: int = 4,
) -> Path:
    """Navigate to the LIVE stream URL, wait for rendering, and capture a full screenshot."""
    logger.info(f"Opening LIVE stream URL: {live_url}")
    await page.goto(live_url, timeout=page_load_timeout * 1000, wait_until="domcontentloaded")

    # Wait for potential video canvas or player elements
    try:
        await page.wait_for_selector("video, canvas, [class*='live-player'], [class*='video-container']", timeout=15000)
        logger.info("Video / Player element detected on page.")
    except Exception:
        logger.warning("Video selector timeout. Proceeding with rendering wait delay.")

    # Additional delay to allow stream frames and UI overlay to settle
    logger.info(f"Waiting {render_delay_seconds} seconds for live video frame rendering...")
    await asyncio.sleep(render_delay_seconds)

    # Save screenshot
    screenshot_file = Path(output_screenshot_path)
    screenshot_file.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(screenshot_file), full_page=False)
    logger.info(f"LIVE screenshot captured successfully and saved to: {screenshot_file.resolve()}")

    return screenshot_file
