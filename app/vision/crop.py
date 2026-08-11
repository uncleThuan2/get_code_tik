import logging
from typing import Tuple
from PIL import Image

logger = logging.getLogger(__name__)

# Precise calibrated ratios based on stream screenshot (Video stream in center container)
# Small code region (covers yellow reward code pills, cutting off left milestone point labels)
DEFAULT_SMALL_REGION = {"x1": 0.28, "y1": 0.02, "x2": 0.37, "y2": 0.32}
# Large code region (pink box CODE GIỚI HẠN / R5XJV9VQ2)
DEFAULT_LARGE_REGION = {"x1": 0.24, "y1": 0.32, "x2": 0.36, "y2": 0.38}


def get_crop_box(img_size: Tuple[int, int], region_cfg: dict) -> Tuple[int, int, int, int]:
    """Convert relative ratio coordinates (0.0 to 1.0) into absolute pixel tuple (left, top, right, bottom)."""
    width, height = img_size
    x1 = int(width * region_cfg.get("x1", 0.20))
    y1 = int(height * region_cfg.get("y1", 0.12))
    x2 = int(width * region_cfg.get("x2", 0.50))
    y2 = int(height * region_cfg.get("y2", 0.40))
    return (x1, y1, x2, y2)


def crop_regions(img: Image.Image, ocr_config: dict = None) -> Tuple[Image.Image, Image.Image]:
    """Crop Small Code region and Large Code region from input screenshot."""
    ocr_cfg = ocr_config or {}
    small_cfg = ocr_cfg.get("small_code_region", DEFAULT_SMALL_REGION)
    large_cfg = ocr_cfg.get("large_code_region", DEFAULT_LARGE_REGION)

    small_box = get_crop_box(img.size, small_cfg)
    large_box = get_crop_box(img.size, large_cfg)

    small_crop = img.crop(small_box)
    large_crop = img.crop(large_box)

    return small_crop, large_crop
