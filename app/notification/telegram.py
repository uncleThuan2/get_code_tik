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


def send_telegram_message(
    message: str,
    bot_token: Optional[str] = None,
    chat_ids: Optional[List[str]] = None,
) -> bool:
    """Send raw text message to Telegram chat(s) via Bot API."""
    tokens = [bot_token] if bot_token else parse_list_from_env("TELEGRAM_BOT_TOKEN")
    targets = chat_ids or parse_list_from_env("TELEGRAM_CHAT_ID")

    if not tokens or not targets:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing. Skipping Telegram message.")
        return False

    overall_success = True
    for token in tokens:
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        for chat_id in targets:
            payload = {
                "chat_id": chat_id,
                "text": message.strip(),
            }
            try:
                response = requests.post(api_url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Telegram notification sent to {chat_id}: '{message.strip()}'")
                else:
                    logger.error(f"Failed to send Telegram message to {chat_id}: {response.text}")
                    overall_success = False
            except Exception as e:
                logger.error(f"Telegram HTTP request error to {chat_id}: {e}")
                overall_success = False

    return overall_success


def send_telegram_photo(
    photo_bytes: bytes,
    caption: str = "",
    bot_token: Optional[str] = None,
    chat_ids: Optional[List[str]] = None,
) -> bool:
    """Send full stream screenshot photo to Telegram chat(s) via Bot API sendPhoto."""
    tokens = [bot_token] if bot_token else parse_list_from_env("TELEGRAM_BOT_TOKEN")
    targets = chat_ids or parse_list_from_env("TELEGRAM_CHAT_ID")

    if not tokens or not targets:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing. Skipping Telegram photo.")
        return False

    overall_success = True
    for token in tokens:
        api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        for chat_id in targets:
            files = {
                "photo": ("stream_screenshot.png", photo_bytes, "image/png")
            }
            data = {
                "chat_id": chat_id,
            }
            if caption:
                data["caption"] = caption.strip()

            try:
                logger.info(f"Sending full stream screenshot photo to Telegram chat_id {chat_id}...")
                response = requests.post(api_url, data=data, files=files, timeout=20)
                if response.status_code == 200:
                    logger.info(f"Telegram stream screenshot photo sent successfully to {chat_id}!")
                else:
                    logger.error(f"Failed to send Telegram photo to {chat_id}: {response.text}")
                    overall_success = False
            except Exception as e:
                logger.error(f"Telegram photo HTTP request error to {chat_id}: {e}")
                overall_success = False

    return overall_success


def notify_new_reward_codes(
    time_label: str = "",
    small_codes: List[str] = None,
    large_codes: List[str] = None,
    screenshot_bytes: Optional[bytes] = None,
) -> bool:
    """Send each detected raw reward code text message first, then send 1 single full stream screenshot photo at the end."""
    codes = (small_codes or []) + (large_codes or [])
    if not codes:
        return True

    success = True
    # 1. Send all raw code text messages 1-by-1
    for code in codes:
        if code and code.strip():
            res = send_telegram_message(code.strip())
            if not res:
                success = False

    # 2. AFTER all text messages are sent, send 1 single full stream screenshot photo for verification
    if screenshot_bytes:
        photo_res = send_telegram_photo(screenshot_bytes, caption=f"📸 Stream verification screenshot ({time_label})")
        if not photo_res:
            logger.warning("Failed to send verification screenshot photo to Telegram.")

    return success
