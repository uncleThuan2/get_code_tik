import logging
import re
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# CSS Selectors for detecting TikTok LIVE on profile page
# Layered selectors to handle TikTok UI variations
LIVE_AVATAR_SELECTORS = [
    'div[data-e2e="user-avatar"] [class*="avatar-live"]',
    'a[href*="/live"]',
    'div[class*="DivLiveBadge"]',
    'span[class*="SpanLiveBadge"]',
    '[data-e2e="user-post-item"] a[href*="/live"]',
    'div[class*="live-tag"]',
]

LIVE_TEXT_PATTERNS = [
    r"LIVE",
    r"Trực tiếp",
    r"watch live",
]


async def open_profile(page: Page, profile_url: str, timeout_seconds: int = 30):
    """Navigate to the TikTok publisher profile URL."""
    logger.info(f"Opening TikTok publisher profile: {profile_url}")
    await page.goto(profile_url, timeout=timeout_seconds * 1000, wait_until="domcontentloaded")
    # Wait for dynamic profile components to render
    await page.wait_for_timeout(3000)


def _get_username_from_url(profile_url: str) -> str:
    """Extract username from profile URL (e.g. '@thegioihoaviencuatoi2026')."""
    clean_url = profile_url.rstrip("/")
    username = clean_url.split("/")[-1]
    if not username.startswith("@"):
        username = f"@{username}"
    return username


async def is_profile_live(page: Page, profile_url: str = "") -> bool:
    """Check if the currently loaded profile is LIVE using user-specific layered detection."""
    username = _get_username_from_url(profile_url) if profile_url else ""

    # Strategy 1: User-specific live link (e.g. href="/@username/live")
    if username:
        user_live_link = await page.query_selector(f'a[href*="{username}/live"]')
        if user_live_link and await user_live_link.is_visible():
            href = await user_live_link.get_attribute("href")
            logger.info(f"Layer 1 match: Found user live link: {href}")
            return True

    # Strategy 2: Live badge on user avatar container
    avatar_selectors = [
        'div[data-e2e="user-avatar"] [class*="live"]',
        'div[data-e2e="user-avatar"] [class*="Live"]',
        'div[class*="ShareHeader"] [class*="live"]',
        'div[class*="AvatarContainer"] [class*="live"]',
        'span[class*="SpanLiveBadge"]',
        'div[class*="DivLiveBadge"]',
    ]

    for selector in avatar_selectors:
        try:
            element = await page.query_selector(selector)
            if element and await element.is_visible():
                logger.info(f"Layer 2 match: Found avatar live indicator using selector '{selector}'")
                return True
        except Exception:
            continue

    # Strategy 3: Check for profile header LIVE text ("ĐANG LIVE", "WATCH LIVE", "LIVE") strictly within user header
    try:
        header_element = await page.query_selector('div[data-e2e="user-header"], div[class*="ShareHeader"]')
        if header_element:
            header_text = await header_element.inner_text()
            if any(term in header_text.upper() for term in ["LIVE", "TRỰC TIẾP"]):
                logger.info(f"Layer 3 match: Found LIVE text inside user header: {header_text[:50]}")
                return True
    except Exception as e:
        logger.warning(f"Error checking header element for LIVE text: {e}")

    logger.info(f"No active LIVE stream detected for user '{username}'.")
    return False


async def extract_live_url(page: Page, profile_url: str) -> Optional[str]:
    """Find and return the current LIVE stream URL for the publisher."""
    username = _get_username_from_url(profile_url)

    # Check for direct user live anchor
    user_live_link = await page.query_selector(f'a[href*="{username}/live"]')
    if user_live_link:
        href = await user_live_link.get_attribute("href")
        if href:
            if href.startswith("http"):
                logger.info(f"Extracted absolute user LIVE URL: {href}")
                return href
            elif href.startswith("/"):
                full_url = f"https://www.tiktok.com{href}"
                logger.info(f"Extracted relative user LIVE URL -> {full_url}")
                return full_url

    # Standard TikTok user LIVE stream URL format
    constructed_url = f"https://www.tiktok.com/{username}/live"
    logger.info(f"Using constructed user LIVE URL format: {constructed_url}")
    return constructed_url

