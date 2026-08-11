import os
import requests
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)

LITTERBOX_API_URL = "https://litterbox.catbox.moe/resources/internals/api.php"


def upload_temp_image_and_get_url(img_data: bytes | Image.Image, expire_hours: str = "1h") -> str:
    """Upload in-memory screenshot bytes directly to Litterbox Storage API (zero disk writes, auto-deletes).
    Returns direct public URL link.
    """
    try:
        if isinstance(img_data, Image.Image):
            buf = io.BytesIO()
            img_data.save(buf, format="PNG")
            img_bytes = buf.getvalue()
        else:
            img_bytes = img_data

        data = {
            "reqtype": "fileupload",
            "time": expire_hours
        }
        files = {
            "fileToUpload": ("stream_frame.png", img_bytes, "image/png")
        }

        logger.info("Uploading in-memory screenshot directly to Litterbox Cloud Storage API...")
        response = requests.post(LITTERBOX_API_URL, data=data, files=files, timeout=15)
        
        if response.status_code == 200:
            direct_url = response.text.strip()
            logger.info(f"Temporary Public URL generated: {direct_url}")
            return direct_url
        else:
            logger.error(f"Litterbox Upload Failed with status {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"Failed to upload in-memory screenshot to Cloud Storage: {e}")

    return ""
