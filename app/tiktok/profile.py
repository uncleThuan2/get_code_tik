import logging
import re
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


def _get_username_from_url(profile_url: str) -> str:
    """Extract username from profile URL (e.g. '@thegioihoaviencuatoi2026')."""
    clean_url = profile_url.rstrip("/")
    username = clean_url.split("/")[-1]
    if not username.startswith("@"):
        username = f"@{username}"
    return username


async def open_profile(page: Page, profile_url: str, timeout_seconds: int = 30):
    """Navigate to the TikTok publisher profile URL."""
    logger.info(f"Opening TikTok publisher profile: {profile_url}")
    await page.goto(profile_url, timeout=timeout_seconds * 1000, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)


async def is_profile_live(page: Page, profile_url: str = "") -> bool:
    """Check if the currently loaded profile is LIVE using strict user avatar indicators."""
    username = _get_username_from_url(profile_url) if profile_url else ""

    # Strategy 1: Check for live avatar link inside user avatar container
    if username:
        # Check inside user avatar container specifically
        avatar_container = await page.query_selector('div[data-e2e="user-avatar"]')
        if avatar_container:
            live_link = await avatar_container.query_selector('a[href*="/live"], [class*="live"]')
            if live_link:
                logger.info(f"Strict Match: Found LIVE indicator inside user-avatar container for {username}")
                return True

    # Strategy 2: Check for explicit avatar live badge elements
    strict_selectors = [
        'div[data-e2e="user-avatar"] [class*="avatar-live"]',
        'div[data-e2e="user-avatar"] [class*="AvatarLive"]',
        'div[class*="DivLiveBadge"]',
        'span[class*="SpanLiveBadge"]',
    ]

    for selector in strict_selectors:
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                logger.info(f"Strict Match: Found LIVE badge selector '{selector}'")
                return True
        except Exception:
            continue

    logger.info(f"No active LIVE stream detected for user '{username}'.")
    return False


async def extract_live_url(page: Page, profile_url: str) -> Optional[str]:
    """Find and return the current LIVE stream URL for the publisher."""
    username = _get_username_from_url(profile_url)

    # Check for direct user live anchor in avatar
    avatar_container = await page.query_selector('div[data-e2e="user-avatar"]')
    if avatar_container:
        user_live_link = await avatar_container.query_selector('a[href*="/live"]')
        if user_live_link:
            href = await user_live_link.get_attribute("href")
            if href:
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    return f"https://www.tiktok.com{href}"

    return f"https://www.tiktok.com/{username}/live"
