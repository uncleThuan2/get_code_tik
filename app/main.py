import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional
from PIL import Image

from app.config import load_config
from app.tiktok.browser import TikTokBrowser
from app.tiktok.live_detector import detect_live_session
from app.tiktok.live_session import enter_and_capture_live_session, hide_tiktok_overlays, detect_and_handle_captcha

from app.vision.ocr import extract_all_codes_from_stream
from app.vision.validator import is_valid_code

from app.storage.daily_file import append_codes_to_daily_file
from app.storage.duplicate_checker import filter_new_codes
from app.storage.cleanup import cleanup_old_daily_files, cleanup_temp_screenshots

from app.notification.telegram import notify_new_reward_codes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def run_ocr_stream_session(browser: TikTokBrowser, config: dict, time_label: str):
    """Direct single-pass capture: enter stream, take screenshot, extract codes via Gemini Vision AI, notify & exit."""
    temp_img_path = Path("screenshots/frame_1.png")

    logger.info("Capturing stream screenshot for Gemini Vision AI...")
    await detect_and_handle_captcha(browser.page)
    await hide_tiktok_overlays(browser.page)
    await browser.take_screenshot(temp_img_path)

    if not temp_img_path.exists():
        logger.error("Failed to capture stream screenshot frame.")
        return

    img = Image.open(temp_img_path)

    # Direct 2-Images + 1-Prompt Gemini Vision AI Extraction
    small_codes_found, large_codes_found = extract_all_codes_from_stream(img)

    logger.info(f"Gemini Vision Extracted -> Small Codes: {small_codes_found} | Large Codes: {large_codes_found}")

    # Filter out duplicates against daily file
    new_small = filter_new_codes(small_codes_found)
    new_large = filter_new_codes(large_codes_found)

    if new_small or new_large:
        logger.info(f"New Reward Codes Detected! Small: {new_small} | Large: {new_large}")
        append_codes_to_daily_file(time_label, new_small, new_large)
        notify_new_reward_codes(time_label, new_small, new_large)
    else:
        logger.info("No new non-duplicate codes detected.")


async def main():
    logger.info("==================================================")
    logger.info("   TIKTOK LIVE REWARD CODE BOT — MAIN EXECUTOR    ")
    logger.info("==================================================")

    # 1. Housekeeping: cleanup old daily files
    cleanup_old_daily_files()

    config = load_config()
    profile_url = config.get("tiktok", {}).get("profile_url")
    live_cfg = config.get("live", {})

    check_interval = live_cfg.get("check_interval_seconds", 10)
    max_wait = live_cfg.get("max_wait_minutes", 5)
    page_load_timeout = live_cfg.get("page_load_timeout_seconds", 30)

    time_label = datetime.now().strftime("%H:%M")

    browser = TikTokBrowser(config)
    try:
        page = await browser.start()
        logger.info(f"Publisher Profile URL: {profile_url}")

        is_live, live_url = await detect_live_session(
            page=page,
            profile_url=profile_url,
            check_interval_seconds=check_interval,
            max_wait_minutes=max_wait,
            page_load_timeout=page_load_timeout,
        )

        try:
            await browser.take_screenshot("screenshots/status_check.png")
        except Exception:
            pass

        if is_live and live_url:
            logger.info(f"Account is LIVE! Entering stream: {live_url}")
            await page.goto(live_url, timeout=page_load_timeout * 1000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Direct Gemini Vision AI Single Pass
            await run_ocr_stream_session(browser, config, time_label)
        else:
            logger.warning(f"Account {profile_url} was NOT LIVE during check window.")
            try:
                await browser.take_screenshot("screenshots/offline_check.png")
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Execution error in main pipeline: {e}", exc_info=True)
    finally:
        await browser.close()

    # Clean up temporary screenshots
    cleanup_temp_screenshots()
    logger.info("Pipeline execution completed cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
