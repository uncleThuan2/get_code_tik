from PIL import Image
from pathlib import Path
from app.vision.crop import crop_regions

img = Image.open("screenshots/live-now.png")
width, height = img.size

# Calibrated exact boxes:
# Small code box (w3qg8mz5)
small_cfg = {"x1": 0.34, "y1": 0.24, "x2": 0.47, "y2": 0.31}
# Large code box (pink box R5XJV9VQ2)
large_cfg = {"x1": 0.31, "y1": 0.31, "x2": 0.46, "y2": 0.37}

small_crop, large_crop = crop_regions(img, {"small_code_region": small_cfg, "large_code_region": large_cfg})

debug_dir = Path("debug")
debug_dir.mkdir(exist_ok=True)
small_crop.save(debug_dir / "precise_small.png")
large_crop.save(debug_dir / "precise_large.png")

print("Cropped precise images.")
