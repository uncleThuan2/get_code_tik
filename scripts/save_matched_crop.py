import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

from app.vision.gemini_ocr import _detect_ui_box_via_template_match, crop_combined_bounding_box


def main():
    project_root = Path(__file__).resolve().parent.parent
    live_path = Path(os.getenv("OCR_IMAGE_PATH", str(project_root / "sample" / "live_inspect.png"))).expanduser()
    sample_path = Path(os.getenv("DEFAULT_SAMPLE_PATH", str(project_root / "sample" / "co_code_lon.png"))).expanduser()

    live_img = Image.open(live_path).convert("RGB")
    ui_box = _detect_ui_box_via_template_match(live_img, str(sample_path))

    out_dir = project_root / "debug"
    out_dir.mkdir(exist_ok=True)

    print(f"Live image: {live_path}")
    print(f"Template: {sample_path}")
    print(f"Matched box: {ui_box}")

    if not ui_box:
        raise RuntimeError("No match found; OpenCV did not detect the reward panel.")

    crop_bytes = crop_combined_bounding_box(live_img, [ui_box])
    if not crop_bytes:
        raise RuntimeError("Failed to crop matched box.")

    output_path = out_dir / "matched_crop.png"
    output_path.write_bytes(crop_bytes)
    print(f"Saved crop to: {output_path}")


if __name__ == "__main__":
    main()
