from pathlib import Path
from app.storage.daily_file import append_codes_to_daily_file, read_daily_codes


def test_daily_file_read_write(tmp_path: Path):
    append_codes_to_daily_file(
        time_label="19:35",
        small_codes=["SMALL1234"],
        large_codes=["LARGE5678"],
        data_dir=tmp_path,
    )

    codes = read_daily_codes(data_dir=tmp_path)
    assert "SMALL1234" in codes
    assert "LARGE5678" in codes
