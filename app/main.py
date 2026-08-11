import asyncio
import logging
import sys
from pathlib import Path

from app.config import load_config
from app.tiktok.browser import TikTokBrowser
from app.tiktok.live_detector import detect_live_session
from app.tiktok.live_session import enter_and_capture_live_session

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("main")


async def run_phase1_poc():
    """Main execution function for Phase 1 POC."""
    logger.info("=== Starting TikTok Reward Code Bot — Phase 1 POC ===")

    config = load_config()
    profile_url = config.get("tiktok", {}).get("profile_url")
    live_config = config.get("live", {})

    check_interval = live_config.get("check_interval_seconds", 10)
    max_wait = live_config.get("max_wait_minutes", 5)
    page_load_timeout = live_config.get("page_load_timeout_seconds", 30)

    browser = TikTokBrowser(config)

    try:
        page = await browser.start()
        logger.info(f"Target Profile URL: {profile_url}")

        is_live, live_url = await detect_live_session(
            page=page,
            profile_url=profile_url,
            check_interval_seconds=check_interval,
            max_wait_minutes=max_wait,
            page_load_timeout=page_load_timeout,
        )

        if is_live and live_url:
            logger.info(f"LIVE Session confirmed. Navigating to LIVE stream: {live_url}")
            screenshot_path = Path("screenshots/live-screenshot.png")
            captured_file = await enter_and_capture_live_session(
                page=page,
                live_url=live_url,
                output_screenshot_path=screenshot_path,
                page_load_timeout=page_load_timeout,
            )
            logger.info(f"Phase 1 POC succeeded! LIVE screenshot captured at {captured_file.resolve()}")
        else:
            logger.warning("Account is currently NOT LIVE. Capturing profile state screenshot...")
            profile_screenshot = Path("screenshots/live-screenshot.png")
            await browser.take_screenshot(profile_screenshot)
            logger.info(f"Profile screenshot saved to {profile_screenshot.resolve()}. Phase 1 completed gracefully.")

    except Exception as e:
        logger.error(f"Fatal error during Phase 1 POC execution: {e}", exc_info=True)
        # Also capture error screenshot if browser is active
        try:
            error_img = Path("screenshots/error-state.png")
            await browser.take_screenshot(error_img)
            logger.info(f"Error state screenshot saved to {error_img.resolve()}")
        except Exception:
            pass
        sys.exit(1)

    finally:
        await browser.close()
        logger.info("=== Phase 1 POC Execution Finished ===")


def main():
    asyncio.run(run_phase1_poc())


if __name__ == "__main__":
    main()
