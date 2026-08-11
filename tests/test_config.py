from app.config import load_config


def test_load_config():
    config = load_config()
    assert "tiktok" in config
    assert config["tiktok"]["profile_url"] == "https://www.tiktok.com/@thegioihoaviencuatoi2026"
    assert "live" in config
    assert "browser" in config
