import asyncio
from pathlib import Path
from PIL import Image

from app.config import load_config
from app.vision.crop import crop_regions

img = Image.open("screenshots/live-now-realtime.png")
width, height = img.size

# Calibrated exact boxes based on centered player:
# Small code box stack column (5000, 3000, 1500, 500)
small_cfg = {"x1": 0.24, "y1": 0.02, "x2": 0.37, "y2": 0.32}
# Large code box (pink box CODE GIỚI HẠN / R5XJV9VQ2)
large_cfg = {"x1": 0.24, "y1": 0.32, "x2": 0.36, "y2": 0.38}

small_crop, large_crop = crop_regions(img, {"small_code_region": small_cfg, "large_code_region": large_cfg})

debug_dir = Path("debug")
debug_dir.mkdir(exist_ok=True)
small_crop.save(debug_dir / "precise_small.png")
large_crop.save(debug_dir / "precise_large.png")

print("Saved centered player precise crops.")
