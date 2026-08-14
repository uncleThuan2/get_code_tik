import json
from io import BytesIO

from PIL import Image

from app.vision import gemini_ocr


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_extract_codes_uses_template_match_and_ocr(monkeypatch):
    calls = []
    gemini_ocr.DEFAULT_SAMPLE_PATH = "https://example.com/live_inspect_match.png"

    image = Image.new("RGB", (100, 100), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    valid_png = buffer.getvalue()

    def fake_upload(img_data, api_key):
        calls.append("upload")
        return "files/test123", "https://example.com/file/test123"

    def fake_delete(file_name, api_key):
        calls.append(f"delete:{file_name}")
        return None

    def fake_crop(img_data, boxes, padding_percent=0.04):
        calls.append("crop")
        return b"cropped-image-bytes"

    def fake_template_match(stream_data, sample_reference=""):
        calls.append("template-match")
        return [10, 20, 30, 40]

    def fake_post(url, headers=None, json=None, payload=None, timeout=None, **kwargs):
        calls.append(f"post:{url}")
        return DummyResponse(
            200,
            {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": __import__("json").dumps({"small_codes": ["w3qg8mz5"], "large_codes": ["HN9KJMEW"]})
                        }]
                    }
                }]
            },
        )

    monkeypatch.setattr(gemini_ocr, "upload_to_google_file_api", fake_upload)
    monkeypatch.setattr(gemini_ocr, "delete_from_google_file_api", fake_delete)
    monkeypatch.setattr(gemini_ocr, "crop_combined_bounding_box", fake_crop)
    monkeypatch.setattr(gemini_ocr, "_detect_ui_box_via_template_match", fake_template_match)
    monkeypatch.setattr(gemini_ocr.requests, "post", fake_post)

    small_codes, large_codes, sample_cropped = gemini_ocr.extract_codes_via_gemini_vision(valid_png, api_key="test-key")

    assert small_codes == ["w3qg8mz5"]
    assert large_codes == ["HN9KJMEW"]
    assert sample_cropped == b"cropped-image-bytes"
    assert "template-match" in calls
    assert "crop" in calls
    assert "upload" in calls
    assert "post:" in str(calls)


def test_extract_codes_ignores_legacy_ui_detection_calls(monkeypatch):
    calls = []
    gemini_ocr.DEFAULT_SAMPLE_PATH = "https://example.com/live_inspect_match.png"

    image = Image.new("RGB", (100, 100), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    valid_png = buffer.getvalue()

    def fake_upload(img_data, api_key):
        calls.append("upload")
        return "files/test123", "https://example.com/file/test123"

    def fake_delete(file_name, api_key):
        calls.append(f"delete:{file_name}")
        return None

    def fake_crop(img_data, boxes, padding_percent=0.04):
        calls.append("crop")
        return b"cropped-image-bytes"

    def fake_template_match(stream_data, sample_reference=""):
        calls.append("template-match")
        return [10, 20, 30, 40]

    def fake_post(url, headers=None, json=None, payload=None, timeout=None, **kwargs):
        calls.append(f"post:{url}")
        return DummyResponse(
            200,
            {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": __import__("json").dumps({"small_codes": ["abc123"], "large_codes": ["XYZ999"]})
                        }]
                    }
                }]
            },
        )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Legacy Gemini UI detection should not be used in the template-match flow")

    monkeypatch.setattr(gemini_ocr, "upload_to_google_file_api", fake_upload)
    monkeypatch.setattr(gemini_ocr, "delete_from_google_file_api", fake_delete)
    monkeypatch.setattr(gemini_ocr, "crop_combined_bounding_box", fake_crop)
    monkeypatch.setattr(gemini_ocr, "_detect_ui_box_via_template_match", fake_template_match)
    monkeypatch.setattr(gemini_ocr, "detect_ui_box_via_gemini_vision", fail_if_called)
    monkeypatch.setattr(gemini_ocr.requests, "post", fake_post)

    small_codes, large_codes, sample_cropped = gemini_ocr.extract_codes_via_gemini_vision(valid_png, api_key="test-key")

    assert small_codes == ["abc123"]
    assert large_codes == ["XYZ999"]
    assert sample_cropped == b"cropped-image-bytes"
    assert "template-match" in calls
    assert "crop" in calls
    assert "upload" in calls


def test_get_default_sample_path_reads_runtime_env(monkeypatch):
    monkeypatch.delenv("DEFAULT_SAMPLE_PATH", raising=False)
    monkeypatch.delenv("SAMPLE_REFERENCE_IMAGE_PATH", raising=False)
    monkeypatch.setenv("GEMINI_SAMPLE_IMAGE_PATH", "sample/co_code_lon.png")
    assert gemini_ocr.get_default_sample_path() == "sample/co_code_lon.png"

    monkeypatch.setenv("DEFAULT_SAMPLE_PATH", "sample/override.png")
    assert gemini_ocr.get_default_sample_path() == "sample/override.png"


def test_crop_combined_bounding_box_handles_normalized_coords():
    image = Image.new("RGB", (1000, 1000), color="white")
    box = [200, 150, 400, 350]

    cropped = gemini_ocr.crop_combined_bounding_box(image, [box])

    assert cropped is not None
    result = Image.open(BytesIO(cropped))
    assert result.size == (280, 280)


def test_delete_from_google_file_api_keeps_default_sample_reference(monkeypatch):
    gemini_ocr.DEFAULT_SAMPLE_PATH = "https://generativelanguage.googleapis.com/v1beta/files/sample-123"
    calls = []

    def fake_delete(url, timeout=None):
        calls.append(url)
        return DummyResponse(200, {})

    monkeypatch.setattr(gemini_ocr.requests, "delete", fake_delete)

    gemini_ocr.delete_from_google_file_api("files/sample-123", "test-key")
    gemini_ocr.delete_from_google_file_api("files/live-456", "test-key")

    assert len(calls) == 1
    assert "live-456" in calls[0]
