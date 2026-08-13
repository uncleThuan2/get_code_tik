import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from app.tiktok.live_session import detect_and_handle_captcha, hide_tiktok_overlays


LIVE_URL = os.getenv("LIVE_URL", "https://www.tiktok.com/@thegioihoaviencuatoi2026/live")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "debug"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1912,1080",
                "--force-device-scale-factor=1",
                "--high-dpi-support=1",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1912, "height": 1080},
            device_scale_factor=1,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )

        page = await context.new_page()
        page.set_default_timeout(60000)

        print(f"Opening: {LIVE_URL}")
        await page.goto(LIVE_URL, wait_until="domcontentloaded", timeout=60000)
        await detect_and_handle_captcha(page)
        await hide_tiktok_overlays(page)
        await page.wait_for_timeout(5000)
        await detect_and_handle_captcha(page)
        await hide_tiktok_overlays(page)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = OUTPUT_DIR / f"live_inspect_{timestamp}.png"
        img_bytes = await page.screenshot(type="png")
        save_path.write_bytes(img_bytes)

        from PIL import Image
        img = Image.open(save_path)
        print(f"Saved screenshot: {save_path}")
        print(f"Image size: {img.size[0]} x {img.size[1]} pixels")
        print(f"Format: {img.format}")

        await page.close()
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
