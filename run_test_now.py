import asyncio
import logging
import os
import sys
from pathlib import Path
from PIL import Image

from app.config import load_config
from app.tiktok.browser import TikTokBrowser
from app.tiktok.live_detector import detect_live_session
from app.tiktok.live_session import enter_and_capture_live_session

# Setup verbose logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("TEST_NOW")


async def main():
    logger.info("==================================================")
    logger.info("  RUNNING LIVE TEST NOW - TIKTOK REWARD CODE BOT  ")
    logger.info("==================================================")

    config = load_config()
    profile_url = config["tiktok"]["profile_url"]

    # Allow local visual debugging by setting HEADLESS=false if desired
    headless = os.environ.get("HEADLESS", "true").lower() in ("true", "1", "yes")
    config["browser"]["headless"] = headless

    logger.info(f"Target Profile: {profile_url}")
    logger.info(f"Headless Mode: {headless}")

    browser = TikTokBrowser(config)
    try:
        page = await browser.start()

        # Step 1: Detect LIVE status
        logger.info("--- Step 1: Checking Profile Live Status ---")
        is_live, live_url = await detect_live_session(
            page=page,
            profile_url=profile_url,
            check_interval_seconds=5,
            max_wait_minutes=1, # Quick check for manual run
            page_load_timeout=30,
        )

        logger.info(f"Result -> Is Live: {is_live} | Live URL: {live_url}")

        target_url = live_url if (is_live and live_url) else profile_url
        if not is_live:
            logger.warning("Account is NOT LIVE right now. Will capture profile page screenshot.")

        # Step 2: Capture stream screenshot
        logger.info("--- Step 2: Capturing Screenshot ---")
        screenshot_path = Path("screenshots/live-now.png")
        await enter_and_capture_live_session(
            page=page,
            live_url=target_url,
            output_screenshot_path=screenshot_path,
            page_load_timeout=30,
            render_delay_seconds=5,
        )

        logger.info(f"[SUCCESS] Screenshot saved to: {screenshot_path.resolve()}")

        # Step 3: Crop code regions for inspection
        if screenshot_path.exists():
            logger.info("--- Step 3: Cropping Code Regions ---")
            debug_dir = Path("debug")
            debug_dir.mkdir(exist_ok=True)

            img = Image.open(screenshot_path)
            width, height = img.size
            logger.info(f"Image Resolution: {width}x{height}")

            # Region A: Small code (Upper section)
            # Coordinates from config: x1: 0.20, y1: 0.30, x2: 0.80, y2: 0.50
            crop_a_box = (
                int(width * 0.20),
                int(height * 0.25),
                int(width * 0.80),
                int(height * 0.48),
            )
            small_crop = img.crop(crop_a_box)
            small_crop_path = debug_dir / "small_code_region.png"
            small_crop.save(small_crop_path)
            logger.info(f"Small Code region cropped -> {small_crop_path.resolve()}")

            # Region B: Large code (Lower section)
            # Coordinates from config: x1: 0.20, y1: 0.50, x2: 0.80, y2: 0.75
            crop_b_box = (
                int(width * 0.20),
                int(height * 0.48),
                int(width * 0.80),
                int(height * 0.75),
            )
            large_crop = img.crop(crop_b_box)
            large_crop_path = debug_dir / "large_code_region.png"
            large_crop.save(large_crop_path)
            logger.info(f"Large Code region cropped -> {large_crop_path.resolve()}")

            # Step 4: Attempt OCR if pytesseract is available
            logger.info("--- Step 4: Attempting OCR ---")
            try:
                import pytesseract

                small_text = pytesseract.image_to_string(small_crop).strip()
                large_text = pytesseract.image_to_string(large_crop).strip()

                logger.info(f"OCR Small Code Region: '{small_text}'")
                logger.info(f"OCR Large Code Region: '{large_text}'")
            except Exception as ocr_err:
                logger.warning(f"PyTesseract OCR notice: {ocr_err}")
                logger.info("Check cropped images in 'debug/' folder for visual inspection.")

    except Exception as e:
        logger.error(f"Error executing test run: {e}", exc_info=True)

    finally:
        await browser.close()
        logger.info("==================================================")
        logger.info("               TEST RUN COMPLETED                 ")
        logger.info("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
