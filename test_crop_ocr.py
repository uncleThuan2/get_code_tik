from PIL import Image
from pathlib import Path
from app.vision.crop import crop_regions

img = Image.open("screenshots/live-now.png")

# Calibrated region covering all 4 chest milestones (5000, 3000, 1500, 500)
small_cfg = {"x1": 0.30, "y1": 0.02, "x2": 0.48, "y2": 0.32}
large_cfg = {"x1": 0.31, "y1": 0.31, "x2": 0.46, "y2": 0.37}

small_crop, large_crop = crop_regions(img, {"small_code_region": small_cfg, "large_code_region": large_cfg})

debug_dir = Path("debug")
debug_dir.mkdir(exist_ok=True)
small_crop.save(debug_dir / "precise_small.png")
large_crop.save(debug_dir / "precise_large.png")

print("Saved precise 4-chest small code crop.")
