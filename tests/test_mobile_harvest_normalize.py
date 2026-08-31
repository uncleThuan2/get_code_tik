from tools.mobile_harvest.bluestacks_trial import FarmGridDetector


def test_normalize_to_standard_centers_and_scales_region():
    detector = FarmGridDetector(left=200, top=400, right=1100, bottom=1200, cols=6, rows=4)

    left, top, right, bottom = detector.normalize_to_standard(screen_width=1536, screen_height=2048)

    assert right - left == detector.DEFAULT_STANDARD_WIDTH
    assert bottom - top == detector.DEFAULT_STANDARD_HEIGHT
    assert left + (right - left) / 2 == 1536 / 2
    assert top + (bottom - top) / 2 == 2048 / 2
