from app.vision.validator import is_valid_code, is_not_released, clean_ocr_text


def test_is_valid_code():
    assert is_valid_code("R5XJV9VQ2") is True
    assert is_valid_code("w3qg8mz5") is True
    assert is_valid_code("ABCD12345") is True

    # Invalid cases
    assert is_valid_code("CODE GIỚI HẠN") is False
    assert is_valid_code("") is False
    assert is_valid_code("SHORT") is False  # less than 6 chars
    assert is_valid_code("VERYLONGTEXT123456789") is False  # more than 16 chars
    assert is_valid_code("CLONING") is False  # pure word without digits
    assert is_valid_code("AIKHANG") is False  # pure word without digits


def test_is_not_released():
    assert is_not_released("CODE GIỚI HẠN") is True
    assert is_not_released("Code Gioi Han, co hieu luc 30 phut") is True
    assert is_not_released("R5XJV9VQ2") is False


def test_clean_ocr_text():
    assert clean_ocr_text(" W3QG 8MZ5 ") == "W3QG8MZ5"
    assert clean_ocr_text("R5XJ-V9VQ2!") == "R5XJV9VQ2"
