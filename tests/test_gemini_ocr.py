import json
from io import BytesIO

from PIL import Image

from app.vision.gemini_ocr import extract_codes_via_gemini_vision


class DummyResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_extract_codes_retries_when_model_is_unavailable(monkeypatch):
    calls = []

    image = Image.new("RGB", (100, 100), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    valid_png = buffer.getvalue()

    def fake_upload(img_data, api_key):
        return "files/test123", "https://example.com/file/test123"

    def fake_delete(file_name, api_key):
        return None

    def fake_post(url, headers=None, payload=None, timeout=None, **kwargs):
        calls.append((url, timeout))
        if len(calls) == 1:
            return DummyResponse(200, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
        return DummyResponse(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": __import__("json").dumps({"ui_box_2d": [10, 20, 30, 40], "small_codes": ["w3qg8mz5"], "large_codes": ["HN9KJMEW"]})}
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.vision.gemini_ocr.upload_to_google_file_api", fake_upload)
    monkeypatch.setattr("app.vision.gemini_ocr.delete_from_google_file_api", fake_delete)
    monkeypatch.setattr("app.vision.gemini_ocr.requests.post", fake_post)

    small_codes, large_codes, sample_cropped = extract_codes_via_gemini_vision(valid_png, api_key="test-key")

    assert small_codes == ["w3qg8mz5"]
    assert large_codes == ["HN9KJMEW"]
    assert sample_cropped is not None
    assert len(calls) == 2


def test_extract_codes_skips_model_removed_by_google(monkeypatch):
    calls = []

    image = Image.new("RGB", (100, 100), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    valid_png = buffer.getvalue()

    def fake_upload(img_data, api_key):
        return "files/test123", "https://example.com/file/test123"

    def fake_delete(file_name, api_key):
        return None

    def fake_post(url, headers=None, payload=None, timeout=None, **kwargs):
        calls.append((url, timeout))
        if "gemini-2.5-flash" in url:
            return DummyResponse(200, {"error": {"code": 404, "message": "This model is no longer available to new users.", "status": "NOT_FOUND"}})
        return DummyResponse(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": __import__("json").dumps({"ui_box_2d": [10, 20, 30, 40], "small_codes": ["w3qg8mz5"], "large_codes": ["HN9KJMEW"]})}
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.vision.gemini_ocr.upload_to_google_file_api", fake_upload)
    monkeypatch.setattr("app.vision.gemini_ocr.delete_from_google_file_api", fake_delete)
    monkeypatch.setattr("app.vision.gemini_ocr.requests.post", fake_post)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

    small_codes, large_codes, sample_cropped = extract_codes_via_gemini_vision(valid_png, api_key="test-key")

    assert small_codes == ["w3qg8mz5"]
    assert large_codes == ["HN9KJMEW"]
    assert sample_cropped is not None
    assert len(calls) >= 2
