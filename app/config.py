import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def load_config(config_path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    """Load configuration from YAML file and apply environment variable overrides."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found at: {config_file.resolve()}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Environment variable overrides
    if "HEADLESS" in os.environ:
        headless_val = os.environ["HEADLESS"].lower() in ("true", "1", "yes")
        if "browser" not in config:
            config["browser"] = {}
        config["browser"]["headless"] = headless_val

    if "TIKTOK_PROFILE_URL" in os.environ:
        if "tiktok" not in config:
            config["tiktok"] = {}
        config["tiktok"]["profile_url"] = os.environ["TIKTOK_PROFILE_URL"]

    return config
