# TikTok Live Reward Code Bot

Automated bot designed to monitor the game publisher's TikTok LIVE session, detect reward codes using Playwright and OCR, prevent duplicates, save daily codes to storage, and notify users via Telegram.

## Publisher Target
- **Profile URL**: `https://www.tiktok.com/@thegioihoaviencuatoi2026`
- Target schedule: 18:35, 19:35, 20:35, 21:35 (Asia/Ho_Chi_Minh timezone)

---

## Current Status: Phase 1 — Proof-of-Concept (POC)

Phase 1 focuses on validating that Playwright Chromium running in a GitHub-hosted runner can:
1. Open the publisher's profile page without fixed `/live` URL dependencies.
2. Detect if the account is currently LIVE.
3. Open the LIVE stream if active.
4. Render the video frame and capture a full screenshot (`screenshots/live-screenshot.png`).
5. Upload the screenshot as a GitHub Actions workflow artifact.

---

## Project Structure

```text
.
├── app/
│   ├── __init__.py
│   ├── main.py                  # Entrypoint orchestrating execution
│   ├── config.py                # Configuration parser
│   └── tiktok/
│       ├── __init__.py
│       ├── browser.py           # Playwright Chromium manager
│       ├── profile.py           # TikTok profile detector
│       ├── live_detector.py     # LIVE detection polling loop
│       └── live_session.py      # Stream rendering & screenshot capture
├── config/
│   └── config.yaml              # App configuration
├── screenshots/                 # Captured live screenshots
├── data/                        # Daily code files (Future Phase)
├── .github/
│   └── workflows/
│       └── reward-code-bot.yml  # GitHub Actions workflow
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── README.md
```

---

## Local Setup & Run

### 1. Requirements
- Python 3.11+
- pip

### 2. Install Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Run Phase 1 Locally
```bash
python -m app.main
```

To run with visible browser UI locally:
```bash
HEADLESS=false python -m app.main
```

---

## GitHub Actions Manual Trigger

1. Go to repository **Actions** tab.
2. Select **TikTok Reward Code Bot - Phase 1 POC**.
3. Click **Run workflow** -> **Run workflow**.
4. Once completed, inspect the job outputs and download the `live-screenshot` artifact.