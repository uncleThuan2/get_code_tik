import cv2
import numpy as np
from PIL import Image
from typing import List


def preprocess_image_variants(pil_img: Image.Image) -> List[Image.Image]:
    """Generate preprocessed variants (grayscale, thresholded, scaled) for robust OCR."""
    # Convert PIL Image to OpenCV BGR numpy array
    open_cv_image = np.array(pil_img.convert("RGB"))
    bgr = open_cv_image[:, :, ::-1].copy()

    # 1. Scale 2.5x for higher DPI
    h, w = bgr.shape[:2]
    scaled = cv2.resize(bgr, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)

    # 2. Grayscale
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)

    # 3. Contrast enhancement (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 4. Otsu Binary Thresholding
    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Inverted Thresholding
    inverted = cv2.bitwise_not(otsu)

    # Convert variants back to PIL Images
    variants = [
        pil_img,
        Image.fromarray(gray),
        Image.fromarray(enhanced),
        Image.fromarray(otsu),
        Image.fromarray(inverted),
    ]

    return variants
