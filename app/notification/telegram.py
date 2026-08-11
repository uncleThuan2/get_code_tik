import logging
import os
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)


def parse_list_from_env(env_name: str) -> List[str]:
    """Parse comma-separated values from environment variable."""
    raw_val = os.environ.get(env_name, "").strip()
    if not raw_val:
        return []
    return [item.strip() for item in raw_val.split(",") if item.strip()]


def format_reward_code_message(
    time_label: str,
    small_codes: List[str] = None,
    large_codes: List[str] = None,
    profile_handle: str = "@thegioihoaviencuatoi2026",
) -> str:
    """Format Telegram message according to spec section 27."""
    small_codes = small_codes or []
    large_codes = large_codes or []

    lines = [
        "🎁 NEW REWARD CODE",
        "",
        f"⏰ {time_label}",
        "",
        "Small Code:",
    ]

    if small_codes:
        for sc in small_codes:
            lines.append(f"`{sc}`")
    else:
        lines.append("Not detected")

    lines.append("")
    lines.append("Large Code:")
    if large_codes:
        for lc in large_codes:
            lines.append(f"`{lc}`")
    else:
        lines.append("Not released / not detected")

    lines.append("")
    lines.append(f"TikTok:\n{profile_handle}")

    return "\n".join(lines)


def send_telegram_message(
    message: str,
    bot_token: Optional[str] = None,
    chat_ids: Optional[List[str]] = None,
) -> bool:
    """Send formatted text message to Telegram chat(s) via Bot API."""
    tokens = [bot_token] if bot_token else parse_list_from_env("TELEGRAM_BOT_TOKEN")
    targets = chat_ids or parse_list_from_env("TELEGRAM_CHAT_ID")

    if not tokens:
        logger.warning("No TELEGRAM_BOT_TOKEN provided. Skipping Telegram notification.")
        return False

    if not targets:
        logger.warning("No TELEGRAM_CHAT_ID provided. Skipping Telegram notification.")
        return False

    overall_success = True

    for token in tokens:
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        for chat_id in targets:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Telegram notification sent successfully to chat_id: {chat_id}")
                else:
                    logger.error(f"Failed to send Telegram message to {chat_id}: Status {response.status_code} - {response.text}")
                    overall_success = False
            except Exception as e:
                logger.error(f"Telegram HTTP request error to {chat_id}: {e}")
                overall_success = False

    return overall_success


def notify_new_reward_codes(
    time_label: str,
    small_codes: List[str] = None,
    large_codes: List[str] = None,
) -> bool:
    """Helper to format and send new reward codes notification."""
    msg = format_reward_code_message(time_label, small_codes, large_codes)
    return send_telegram_message(msg)
