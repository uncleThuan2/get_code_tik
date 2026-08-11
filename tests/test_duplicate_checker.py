import shutil
from pathlib import Path
from app.storage.daily_file import append_codes_to_daily_file
from app.storage.duplicate_checker import is_duplicate_code, filter_new_codes


def test_duplicate_checker(tmp_path: Path):
    # Write initial codes
    append_codes_to_daily_file(
        time_label="18:35",
        small_codes=["W3QG8MZ5"],
        large_codes=["R5XJV9VQ2"],
        data_dir=tmp_path,
    )

    # Test duplication checks
    assert is_duplicate_code("W3QG8MZ5", data_dir=tmp_path) is True
    assert is_duplicate_code("R5XJV9VQ2", data_dir=tmp_path) is True
    assert is_duplicate_code("NEWCODE123", data_dir=tmp_path) is False

    # Test filter_new_codes
    new_candidates = ["W3QG8MZ5", "BRANDNEW123"]
    filtered = filter_new_codes(new_candidates, data_dir=tmp_path)
    assert filtered == ["BRANDNEW123"]
