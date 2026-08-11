import asyncio
import logging
from pathlib import Path
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def hide_tiktok_overlays(page: Page):
    """Hide TikTok player UI overlays (+ Follow banner, headers, popups) to reveal full stream video."""
    try:
        await page.evaluate("""() => {
            const selectors = [
                '[data-e2e="user-info"]',
                '[class*="DivOwnerContainer"]',
                '[class*="DivHeaderContainer"]',
                '[class*="DivLivePlayerHeader"]',
                'button[class*="ButtonFollow"]',
                '[class*="FollowContainer"]',
                '[class*="DivUserContainer"]',
                '[class*="DivModal"]',
                '[class*="DivLoginGuide"]',
                '[class*="DivMask"]',
                '[class*="login-container"]',
                '[class*="DivBottomBanner"]',
                '[id*="sec-sdk"]',
                '[class*="sec-sdk"]',
                '[class*="captcha"]',
                '[class*="verify"]',
                '[class*="challenge"]',
                'iframe[src*="captcha"]'
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                });
            });
        }""")
        logger.debug("Successfully hid TikTok player overlays.")
    except Exception as e:
        logger.warning(f"Failed to hide overlays: {e}")


async def detect_and_handle_captcha(page: Page) -> bool:
    """Check if CAPTCHA verification challenge is detected on page. If found, reload the page."""
    try:
        captcha_detected = await page.evaluate("""() => {
            const captchaSelectors = [
                '[id*="sec-sdk"]',
                '[class*="sec-sdk"]',
                '[class*="captcha"]',
                '[class*="verify"]',
                '[class*="challenge"]',
                'iframe[src*="captcha"]'
            ];
            for (let sel of captchaSelectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetWidth > 0 && el.offsetHeight > 0) {
                    return true;
                }
            }
            const bodyText = document.body ? document.body.innerText : '';
            if (bodyText.includes('Chọn 2 đối tượng') || bodyText.includes('Select 2 objects')) {
                return true;
            }
            return false;
        }""")

        if captcha_detected:
            logger.warning("CAPTCHA verification popup detected! Resetting page (page.reload())...")
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await hide_tiktok_overlays(page)
            return True
    except Exception as e:
        logger.warning(f"Error checking CAPTCHA status: {e}")
    return False


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

    # Hide TikTok player overlays
    await hide_tiktok_overlays(page)

    # Additional delay to allow stream frames to settle
    logger.info(f"Waiting {render_delay_seconds} seconds for live video frame rendering...")
    await asyncio.sleep(render_delay_seconds)

    # Re-apply overlay hiding right before screenshot
    await hide_tiktok_overlays(page)

    # Save screenshot
    screenshot_file = Path(output_screenshot_path)
    screenshot_file.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(screenshot_file), full_page=False)
    logger.info(f"LIVE screenshot captured successfully and saved to: {screenshot_file.resolve()}")

    return screenshot_file
