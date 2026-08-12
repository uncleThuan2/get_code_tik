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


def notify_new_reward_codes(
    time_label: str = "",
    small_codes: List[str] = None,
    large_codes: List[str] = None,
) -> bool:
    """Send each detected reward code in a separate Telegram message (raw code text only, no extra text/formatting)."""
    codes = (small_codes or []) + (large_codes or [])
    if not codes:
        return True

    success = True
    for code in codes:
        if code and code.strip():
            # Send each raw code in a separate clean message
            res = send_telegram_message(code.strip())
            if not res:
                success = False

    return success
