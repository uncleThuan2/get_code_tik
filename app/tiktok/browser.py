import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class TikTokBrowser:
    """Browser manager wrapping Playwright Chromium instance."""

    def __init__(self, config: dict):
        self.config = config.get("browser", {})
        self.headless: bool = self.config.get("headless", True)
        self.viewport: dict = self.config.get("viewport", {"width": 1912, "height": 1080})
        self.user_agent: str = self.config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self) -> Page:
        """Initialize Playwright, launch Chromium, create context and return Page."""
        logger.info(f"Launching Chromium (headless={self.headless})...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--incognito",
                "--window-size=1912,1080",
                "--force-device-scale-factor=1",
                "--high-dpi-support=1",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1912, "height": 1080},
            device_scale_factor=1,
            user_agent=self.user_agent,
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        # Stealth init script to mask automation flags & enforce incognito environment
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(30000)
        return self._page

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    async def take_screenshot(self, output_path: str | Path, full_page: bool = False) -> Path:
        """Capture screenshot of the current page state."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=str(out_file), full_page=full_page)
        logger.info(f"Screenshot saved to: {out_file.resolve()}")
        return out_file

    async def close(self):
        """Clean up page, context, browser, and playwright resources."""
        if self._page:
            try:
                await self._page.close()
            except Exception as e:
                logger.warning(f"Error closing page: {e}")
            self._page = None

        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None

        logger.info("Browser resources closed cleanly.")
