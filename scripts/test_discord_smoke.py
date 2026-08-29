from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.notification.discord import send_discord_file, send_discord_message


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        raise FileNotFoundError(f"Missing .env file at: {env_path}")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_sample_bytes(sample_path: Path) -> bytes:
    if not sample_path.exists():
        raise FileNotFoundError(f"Sample image not found: {sample_path}")
    return sample_path.read_bytes()


def main() -> int:
    env_path = ROOT / ".env"
    load_env_file(env_path)

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    channel_id = os.getenv("DISCORD_CHANNEL_ID", "").strip()

    if not token or not channel_id:
        raise RuntimeError("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID must be set in .env")

    sample_path = ROOT / "sample" / "co_code_lon.png"
    sample_bytes = read_sample_bytes(sample_path)

    print("[1/2] Sending Discord text message...")
    text_ok = send_discord_message("Hello from smoke test — Discord bot works.")
    print(f"Text result: {'OK' if text_ok else 'FAILED'}")

    print("[2/2] Sending Discord sample image...")
    image_ok = send_discord_file(
        sample_bytes,
        filename="code_sample_smoke.png",
        caption="Smoke test image from sample/co_code_lon.png",
    )
    print(f"Image result: {'OK' if image_ok else 'FAILED'}")

    return 0 if text_ok and image_ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
