import asyncio
from pathlib import Path
from PIL import Image

from app.config import load_config
from app.vision.crop import crop_regions
from app.tiktok.browser import TikTokBrowser
from app.tiktok.live_session import hide_tiktok_overlays


async def main():
    print("=== Generating Live Screenshots and Precise Code Crops ===")

    debug_dir = Path("debug")
    debug_dir.mkdir(exist_ok=True)
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)

    config = load_config()
    config["browser"]["headless"] = True
    browser = TikTokBrowser(config)

    screenshot_path = screenshots_dir / "live-now.png"

    # Try live session if live, otherwise use captured live frame
    try:
        page = await browser.start()
        profile_url = config["tiktok"]["profile_url"]
        print(f"Checking TikTok profile: {profile_url}...")
        await page.goto(profile_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        user_live_link = await page.query_selector('a[href*="/live"]')
        if user_live_link and await user_live_link.is_visible():
            href = await user_live_link.get_attribute("href")
            live_url = f"https://www.tiktok.com{href}" if href.startswith("/") else href
            print(f"Navigating to LIVE stream: {live_url}...")
            await page.goto(live_url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(4)
            await hide_tiktok_overlays(page)
            await asyncio.sleep(1)
            await page.screenshot(path=str(screenshot_path))
            print("Captured fresh live stream screenshot!")
        else:
            print("Channel is offline right now. Processing verified live stream frame...")
    except Exception as e:
        print(f"Notice during live check: {e}")
    finally:
        await browser.close()

    # Process and crop regions from live screenshot
    if screenshot_path.exists():
        img = Image.open(screenshot_path)
        print(f"Loaded screenshot resolution: {img.size[0]}x{img.size[1]}")

        small_crop, large_crop = crop_regions(img, config.get("ocr", {}))

        small_path = debug_dir / "precise_small.png"
        large_path = debug_dir / "precise_large.png"

        small_crop.save(small_path)
        large_crop.save(large_path)

        print(f"[1] Full Live Screenshot: {screenshot_path.resolve()}")
        print(f"[2] Precise Small Region (5000->500 pts): {small_path.resolve()}")
        print(f"[3] Precise Large Region: {large_path.resolve()}")
        print("=== Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
