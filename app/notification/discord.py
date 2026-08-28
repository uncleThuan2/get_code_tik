import logging
import os
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


def parse_list_from_env(env_name: str) -> List[str]:
    """Parse comma-separated values from environment variable."""
    raw_val = os.environ.get(env_name, "").strip()
    if not raw_val:
        return []
    return [item.strip() for item in raw_val.split(",") if item.strip()]


def send_discord_message(
    message: str,
    bot_tokens: Optional[List[str]] = None,
    channel_ids: Optional[List[str]] = None,
) -> bool:
    """Send raw text message to Discord channel(s) via Bot API."""
    tokens = bot_tokens or parse_list_from_env("DISCORD_BOT_TOKEN")
    targets = channel_ids or parse_list_from_env("DISCORD_CHANNEL_ID")

    if not tokens or not targets:
        logger.warning("DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID missing. Skipping Discord message.")
        return False

    overall_success = True
    for token in tokens:
        for channel_id in targets:
            api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            headers = {
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "content": message.strip()[:2000],
            }
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=10)
                if response.status_code in (200, 201, 204):
                    logger.info(f"Discord notification sent to channel {channel_id}: '{message.strip()}'")
                else:
                    logger.error(f"Failed to send Discord message to channel {channel_id}: {response.text}")
                    overall_success = False
            except Exception as e:
                logger.error(f"Discord HTTP request error to channel {channel_id}: {e}")
                overall_success = False

    return overall_success


def send_discord_file(
    file_bytes: bytes,
    filename: str,
    caption: str = "",
    bot_tokens: Optional[List[str]] = None,
    channel_ids: Optional[List[str]] = None,
) -> bool:
    """Send a single file to Discord channel(s) via Bot API."""
    tokens = bot_tokens or parse_list_from_env("DISCORD_BOT_TOKEN")
    targets = channel_ids or parse_list_from_env("DISCORD_CHANNEL_ID")

    if not tokens or not targets:
        logger.warning("DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID missing. Skipping Discord file.")
        return False

    overall_success = True
    for token in tokens:
        for channel_id in targets:
            api_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            headers = {
                "Authorization": f"Bot {token}",
            }
            data = {
                "content": caption.strip()[:2000] if caption else "",
            }
            files = {
                "file": (filename, file_bytes, "image/png"),
            }
            try:
                logger.info(f"Sending 1 single cropped sample photo to Discord channel {channel_id}...")
                response = requests.post(api_url, headers=headers, data=data, files=files, timeout=20)
                if response.status_code in (200, 201, 204):
                    logger.info(f"Discord cropped sample photo sent successfully to channel {channel_id}!")
                else:
                    logger.error(f"Failed to send Discord file to channel {channel_id}: {response.text}")
                    overall_success = False
            except Exception as e:
                logger.error(f"Discord file HTTP request error to channel {channel_id}: {e}")
                overall_success = False

    return overall_success


def notify_discord_reward_codes(
    time_label: str = "",
    small_codes: Optional[List[str]] = None,
    large_codes: Optional[List[str]] = None,
    sample_cropped_bytes: Optional[bytes] = None,
) -> bool:
    """Send each reward code as a Discord message, then send exactly one sample image at the end."""
    codes = (small_codes or []) + (large_codes or [])
    if not codes:
        return True

    success = True
    for code in codes:
        if code and code.strip():
            res = send_discord_message(code.strip())
            if not res:
                success = False

    if sample_cropped_bytes:
        photo_res = send_discord_file(
            sample_cropped_bytes,
            filename="code_sample_crop.png",
            caption=f"📸 Verification Sample Crop ({time_label})",
        )
        if not photo_res:
            logger.warning("Failed to send 1 single verification sample photo to Discord.")

    return success
