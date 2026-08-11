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
from app.tiktok.live_session import enter_and_capture_live_session

from app.vision.crop import crop_regions
from app.vision.ocr import extract_code_from_crop
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

logger = logging.getLogger("main")


async def run_ocr_stream_session(browser: TikTokBrowser, config: dict, time_label: str):
    """Run screenshot & OCR scan loop during live stream session."""
    ocr_cfg = config.get("ocr", {})
    screenshot_interval = ocr_cfg.get("screenshot_interval_seconds", 2)
    max_session_minutes = ocr_cfg.get("max_session_minutes", 5)
    confirmation_frames_needed = ocr_cfg.get("confirmation_frames", 2)

    total_duration_seconds = max_session_minutes * 60
    end_time = asyncio.get_event_loop().time() + total_duration_seconds

    # Confirmation tracking buffers: code_candidate -> consecutive_count
    small_candidates: Dict[str, int] = {}
    large_candidates: Dict[str, int] = {}

    confirmed_small_codes: Set[str] = set()
    confirmed_large_codes: Set[str] = set()

    frame_count = 0
    logger.info(f"Starting OCR session loop (Max duration: {max_session_minutes}m, Interval: {screenshot_interval}s)")

    while asyncio.get_event_loop().time() < end_time:
        frame_count += 1
        temp_img_path = Path(f"screenshots/frame_{frame_count}.png")

        try:
            await browser.take_screenshot(temp_img_path)
            if not temp_img_path.exists():
                await asyncio.sleep(screenshot_interval)
                continue

            img = Image.open(temp_img_path)
            small_crop, large_crop = crop_regions(img, ocr_cfg)

            # Process Small Code crop
            small_candidate, _ = extract_code_from_crop(small_crop)
            if small_candidate:
                count = small_candidates.get(small_candidate, 0) + 1
                small_candidates[small_candidate] = count
                logger.info(f"Frame {frame_count}: Small Code candidate '{small_candidate}' (Confirmed {count}/{confirmation_frames_needed})")
                if count >= confirmation_frames_needed:
                    confirmed_small_codes.add(small_candidate)
            else:
                small_candidates.clear()

            # Process Large Code crop
            large_candidate, is_not_rel = extract_code_from_crop(large_crop)
            if large_candidate and not is_not_rel:
                count = large_candidates.get(large_candidate, 0) + 1
                large_candidates[large_candidate] = count
                logger.info(f"Frame {frame_count}: Large Code candidate '{large_candidate}' (Confirmed {count}/{confirmation_frames_needed})")
                if count >= confirmation_frames_needed:
                    confirmed_large_codes.add(large_candidate)
            else:
                large_candidates.clear()

        except Exception as e:
            logger.warning(f"Frame {frame_count} processing error: {e}")

        await asyncio.sleep(screenshot_interval)

    logger.info(f"OCR session ended after {frame_count} frames.")
    logger.info(f"Confirmed Small Codes: {list(confirmed_small_codes)}")
    logger.info(f"Confirmed Large Codes: {list(confirmed_large_codes)}")

    # Filter out duplicates against daily file
    new_small = filter_new_codes(list(confirmed_small_codes))
    new_large = filter_new_codes(list(confirmed_large_codes))

    if new_small or new_large:
        logger.info(f"New Reward Codes Detected! Small: {new_small} | Large: {new_large}")
        # Save to daily file
        append_codes_to_daily_file(time_label, new_small, new_large)
        # Send Telegram notification
        notify_new_reward_codes(time_label, new_small, new_large)
    else:
        logger.info("No new non-duplicate codes detected during this session.")


async def main_pipeline():
    """Complete Bot Main Execution Pipeline."""
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

        if is_live and live_url:
            logger.info(f"Account is LIVE! Entering stream: {live_url}")
            await page.goto(live_url, timeout=page_load_timeout * 1000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Run OCR loop
            await run_ocr_stream_session(browser, config, time_label)
        else:
            logger.warning(f"Account {profile_url} was NOT LIVE during {max_wait} minutes check window.")

    except Exception as e:
        logger.error(f"Execution error in main pipeline: {e}", exc_info=True)
    finally:
        await browser.close()
        cleanup_temp_screenshots()
        logger.info("==================================================")
        logger.info("            BOT EXECUTION FINISHED                ")
        logger.info("==================================================")


def main():
    asyncio.run(main_pipeline())


if __name__ == "__main__":
    main()
