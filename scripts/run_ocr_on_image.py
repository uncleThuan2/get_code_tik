import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

from app.vision.ocr import extract_all_codes_from_stream


def main():
    project_root = Path(__file__).resolve().parent.parent
    default_image = project_root / "sample" / "live_inspect.png"

    image_path = Path(os.getenv("OCR_IMAGE_PATH", str(default_image))).expanduser()

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = Image.open(image_path).convert("RGB")
    print(f"Loading image: {image_path}")
    print(f"Image size: {image.size}")

    small_codes, large_codes, cropped = extract_all_codes_from_stream(image)

    print("\nRESULT:")
    print("small_codes:", small_codes)
    print("large_codes:", large_codes)
    print("cropped_bytes_available:", cropped is not None)
    if cropped is not None:
        print("cropped_bytes_length:", len(cropped))


if __name__ == "__main__":
    main()
