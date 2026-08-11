# TikTok Live Reward Code Bot — Development Specification

## 1. Objective

Build a Python bot that automatically enters the game publisher's TikTok LIVE sessions, detects reward codes displayed on the stream, filters duplicates, stores newly detected codes in a daily `.txt` file, and sends new codes to the user through Telegram.

The final deployment target is **GitHub Actions**. The bot must not require a local Windows machine, `.bat` files, or a continuously running local process.

The project must be implemented incrementally. **Do not build everything blindly in one pass. Start with Phase 1 POC and verify it before proceeding.**

---

## 2. Publisher TikTok Profile

Fixed profile URL:

```text
https://www.tiktok.com/@thegioihoaviencuatoi2026
```

Do NOT hard-code a specific `/live` URL.

The LIVE URL may change every day. The bot must:

1. Open the publisher profile.
2. Detect whether the account is currently LIVE.
3. Find the current LIVE entry.
4. Open that LIVE.

Example:

```text
Day 1:
Profile -> LIVE A

Day 2:
Profile -> LIVE B

Day 3:
Profile -> LIVE C
```

The profile URL remains the same.

---

## 3. Reward Release Schedule

There are four expected reward release times every evening:

```text
18:30
19:30
20:30
21:30
```

The bot must enter the LIVE **5 minutes after** each release:

```text
18:35
19:35
20:35
21:35
```

Mapping:

```text
18:35 -> process 18:30 release
19:35 -> process 19:30 release
20:35 -> process 20:30 release
21:35 -> process 21:30 release
```

Timezone:

```text
Asia/Ho_Chi_Minh
```

Do not make the release time dynamically calculated. The +5 minute offset is intentional and fixed.

---

## 4. GitHub Actions Schedule

Use GitHub Actions Scheduled Workflow.

Preferred schedule:

```yaml
schedule:
  - cron: "35 18 * * *"
  - cron: "35 19 * * *"
  - cron: "35 20 * * *"
  - cron: "35 21 * * *"
```

Configure the workflow timezone as `Asia/Ho_Chi_Minh` if supported by the current GitHub Actions syntax.

If timezone configuration is unavailable, convert to UTC:

```text
18:35 Vietnam = 11:35 UTC
19:35 Vietnam = 12:35 UTC
20:35 Vietnam = 13:35 UTC
21:35 Vietnam = 14:35 UTC
```

The workflow must also support:

```yaml
workflow_dispatch:
```

for manual testing.

---

# 5. High-Level Architecture

```text
GitHub Actions
      |
      v
Python application
      |
      v
Playwright
      |
      v
Chromium
      |
      v
TikTok publisher profile
      |
      v
Detect LIVE
      |
      +---- NOT LIVE ---> retry every 10 seconds
      |
      v
Open current LIVE
      |
      v
Wait for rendering
      |
      v
Screenshot loop
      |
      v
OpenCV crop
      |
      +---- Region A -> Small code
      |
      +---- Region B -> Large code
      |
      v
OCR
      |
      v
Validate
      |
      v
Multi-frame confirmation
      |
      v
Duplicate checker
      |
      +---- Already exists -> ignore
      |
      v
Daily TXT storage
      |
      v
Telegram notification
      |
      v
Git commit/push
```

---

# 6. Technology Stack

Use:

- Python 3.11+
- Playwright
- Chromium
- OpenCV
- Tesseract OCR or EasyOCR
- Pillow
- PyYAML
- Telegram Bot API / `python-telegram-bot`
- pytest

Prefer **Playwright** over Selenium.

Do not use TikTok API unless there is a strong technical reason and it is officially/legally available for the required use case.

The primary approach is browser rendering + screenshot + OCR.

Do not attempt to bypass CAPTCHA, login challenges, anti-bot protections, or other TikTok security mechanisms.

---

# 7. Repository Structure

Create:

```text
tiktok-reward-code-bot/
|
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── scheduler.py
│   │
│   ├── tiktok/
│   │   ├── __init__.py
│   │   ├── browser.py
│   │   ├── profile.py
│   │   ├── live_detector.py
│   │   └── live_session.py
│   │
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── screenshot.py
│   │   ├── crop.py
│   │   ├── preprocess.py
│   │   ├── ocr.py
│   │   └── validator.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── daily_file.py
│   │   └── duplicate_checker.py
│   │
│   └── notification/
│       ├── __init__.py
│       └── telegram.py
│
├── config/
│   └── config.yaml
│
├── data/
│   └── .gitkeep
│
├── tests/
│   ├── test_validator.py
│   ├── test_duplicate_checker.py
│   ├── test_daily_file.py
│   └── test_ocr.py
│
├── screenshots/
│   └── .gitkeep
│
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── .gitignore
│
└── .github/
    └── workflows/
        └── reward-code-bot.yml
```

---

# 8. Configuration

Create:

```text
config/config.yaml
```

Suggested configuration:

```yaml
tiktok:
  profile_url: "https://www.tiktok.com/@thegioihoaviencuatoi2026"

schedule:
  timezone: "Asia/Ho_Chi_Minh"
  release_times:
    - "18:30"
    - "19:30"
    - "20:30"
    - "21:30"
  enter_offset_minutes: 5

live:
  check_interval_seconds: 10
  max_wait_minutes: 5
  page_load_timeout_seconds: 30

ocr:
  screenshot_interval_seconds: 2
  max_session_minutes: 5
  confirmation_frames: 2

storage:
  directory: "data"

telegram:
  enabled: true

cleanup:
  delete_previous_days: true
```

Never store Telegram credentials in this file.

---

# 9. Browser Module

File:

```text
app/tiktok/browser.py
```

Responsibilities:

- Launch Chromium using Playwright.
- Configure headless mode.
- Configure viewport.
- Configure timeouts.
- Provide screenshot capability.
- Cleanly close browser/context/page.

Support an environment variable such as:

```text
HEADLESS=true
```

For GitHub Actions the default should be headless.

For local debugging, allow:

```text
HEADLESS=false
```

if possible.

---

# 10. TikTok Profile Detection

File:

```text
app/tiktok/profile.py
```

The bot opens:

```text
https://www.tiktok.com/@thegioihoaviencuatoi2026
```

It must not assume a fixed LIVE URL.

Provide functions similar to:

```python
async def open_profile(page, profile_url):
    ...

async def get_live_url(page):
    ...

async def is_live(page):
    ...
```

TikTok frontend selectors can change. Do not depend on a single CSS selector.

Use a layered detection strategy:

1. DOM-based LIVE indicators.
2. Current LIVE link detection.
3. Known semantic/accessibility attributes when available.
4. Screenshot/visual fallback if practical.

The implementation should isolate selectors in one place so they can be updated easily.

---

# 11. LIVE Detection

File:

```text
app/tiktok/live_detector.py
```

Interface:

```python
async def is_live(page) -> bool:
    ...

async def get_live_url(page) -> str | None:
    ...
```

Logic:

```text
Open profile
    |
    v
Is LIVE?
    |
    +-- YES --> get LIVE URL --> enter LIVE
    |
    +-- NO
          |
          v
       wait 10 sec
          |
          v
       retry
```

Maximum wait:

```text
5 minutes
```

If no LIVE is detected after 5 minutes:

- log a warning;
- optionally send a Telegram status notification;
- exit gracefully;
- do not mark the workflow as a fatal application error.

---

# 12. LIVE Session

File:

```text
app/tiktok/live_session.py
```

After finding the current LIVE:

```text
Open LIVE
    |
    v
Wait for page
    |
    v
Wait for video/rendering
    |
    v
Wait an additional 3-5 seconds
    |
    v
Start screenshot loop
```

Do not download the entire livestream.

Only screenshots are needed.

---

# 13. Screenshot Loop

Take screenshots every:

```text
2 seconds
```

Maximum session duration:

```text
5 minutes
```

Example:

```text
19:35:00 screenshot
19:35:02 screenshot
19:35:04 screenshot
...
```

The purpose is to detect a code as soon as it appears.

If a new small code appears during the session, it should be detected and sent even if it was not the large-code release.

---

# 14. Two OCR Regions

The user supplied two reference images:

```text
chua_code_lon.png
co_code_lon.png
```

Use these images to identify the two important areas.

There are two logical regions:

### Region A — Small Code

The smaller reward code displayed in the upper area.

### Region B — Large Code

The large/limited code displayed in the lower area.

The bot should OCR these regions independently.

Do not OCR the entire screen unless needed as a fallback.

---

# 15. Region Coordinates

Do not make the implementation depend on one fixed screen resolution.

Prefer normalized/relative coordinates based on viewport width and height.

Example concept:

```python
x1 = width * 0.20
y1 = height * 0.30
x2 = width * 0.80
y2 = height * 0.50
```

The exact coordinates must be determined from the actual TikTok LIVE rendering during POC/testing.

Make regions configurable.

For example:

```yaml
ocr:
  small_code_region:
    x1: 0.20
    y1: 0.30
    x2: 0.80
    y2: 0.50

  large_code_region:
    x1: 0.20
    y1: 0.50
    x2: 0.80
    y2: 0.75
```

Do not assume these example values are final. Calibrate them using screenshots.

---

# 16. OCR Preprocessing

Pipeline:

```text
Screenshot
    |
    v
Crop region
    |
    v
Resize 2x or 3x
    |
    v
Grayscale
    |
    v
Contrast enhancement
    |
    v
Threshold
    |
    v
OCR
```

Try multiple preprocessing variants if recognition quality is poor:

- original
- grayscale
- binary threshold
- adaptive threshold

Select the most reliable result.

---

# 17. Small Code OCR

Example:

```text
w3qg8mz5
```

Normalize OCR result:

```text
strip whitespace
remove accidental spaces
remove punctuation
normalize case if appropriate
```

Example:

```text
W3QG 8MZ5
```

becomes:

```text
W3QG8MZ5
```

Do not automatically replace ambiguous characters such as `O/0` or `I/1` unless evidence from multiple frames supports the correction.

---

# 18. Large Code OCR

Before release, the region may contain:

```text
CODE GIỚI HẠN
```

Treat this as:

```text
NOT_RELEASED
```

Do not store or send it.

After release, the region should contain a real code such as:

```text
R5XJV9VQ2
```

That should be validated before being accepted.

The exact placeholder text may have OCR variations, so detect the concept robustly rather than matching only one exact OCR string.

---

# 19. Code Validation

File:

```text
app/vision/validator.py
```

Provide:

```python
def is_valid_code(code: str) -> bool:
    ...
```

Initial generic validation:

```regex
^[A-Za-z0-9]{6,16}$
```

Validation must reject:

- `CODE GIỚI HẠN`
- common UI text
- empty strings
- strings containing spaces after normalization
- obvious non-code text

Do not make the regex unnecessarily strict until real OCR samples are available.

Make validation configurable.

---

# 20. Multi-Frame Confirmation

Never send a code based on one OCR frame.

A candidate code must appear consistently in at least:

```text
2 consecutive frames
```

Example:

```text
Frame 1 -> R5XJV9VQ2
Frame 2 -> R5XJV9VQ2
```

Accept.

Example:

```text
Frame 1 -> R5XJV9VQ2
Frame 2 -> R5XVJ9V2
```

Do not accept yet. Continue scanning.

This reduces OCR false positives.

---

# 21. Duplicate Detection

File:

```text
app/storage/duplicate_checker.py
```

Before sending any code:

```text
code_exists(code)
```

If code already exists in today's file:

```text
SKIP
```

If code does not exist:

```text
SAVE
SEND
```

The duplicate check must apply independently to both small and large codes.

---

# 22. Daily TXT Storage

Directory:

```text
data/
```

Filename:

```text
YYYY-MM-DD.txt
```

Example:

```text
data/2026-08-11.txt
```

Suggested content:

```text
=== 18:35 ===

Small Code:
W3QG8MZ5

Large Code:
R5XJV9VQ2


=== 19:35 ===

Small Code:
ABCD1234

Large Code:
X8K2PQ91
```

If only a small code is detected:

```text
=== 20:35 ===

Small Code:
ABC12345

Large Code:
NOT_FOUND
```

The file is the authoritative duplicate-check source.

---

# 23. File Safety

Use atomic writes where practical:

```text
write temporary file
    |
    v
flush
    |
    v
rename to target
```

Avoid leaving a partially written daily file if the process is interrupted.

---

# 24. GitHub Persistence

GitHub Actions runners are ephemeral.

Therefore the daily file must be persisted in the repository.

Workflow:

```text
checkout repository
    |
    v
read existing data/YYYY-MM-DD.txt
    |
    v
run bot
    |
    v
update daily file
    |
    v
git diff
    |
    v
commit
    |
    v
push
```

Commit message:

```text
chore: update reward codes for YYYY-MM-DD
```

If there is no change, do not create an empty commit.

---

# 25. GitHub Permissions

Workflow must request only the required permission:

```yaml
permissions:
  contents: write
```

Use the default `GITHUB_TOKEN` if sufficient.

Do not create a Personal Access Token unless there is a demonstrated need.

---

# 26. Telegram

Use Telegram for notifications.

Credentials must be stored as GitHub Actions Secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Never put them in source code, YAML configuration, screenshots, logs, or committed files.

---

# 27. Telegram Message Format

For new codes:

```text
🎁 NEW REWARD CODE

⏰ 19:35

Small Code:
W3QG8MZ5

Large Code:
R5XJV9VQ2

TikTok:
@thegioihoaviencuatoi2026
```

If only a small code exists:

```text
🎁 NEW REWARD CODE

⏰ 19:35

Small Code:
W3QG8MZ5

Large Code:
Not released / not detected
```

If multiple new codes are detected:

```text
🎁 NEW REWARD CODES

⏰ 19:35

Small:
W3QG8MZ5
ABCD1234

Large:
R5XJV9VQ2
```

Only include codes that are genuinely new.

---

# 28. Notification Failure

If Telegram fails:

```text
Code must still be saved to the daily TXT.
```

Do not lose a code just because Telegram is temporarily unavailable.

Log the Telegram error.

Optionally retry Telegram once or twice.

---

# 29. Cleanup

The user only needs daily files for duplicate filtering.

Delete previous-day files.

Example:

```text
Today:
data/2026-08-12.txt

Delete:
data/2026-08-11.txt
```

A cleanup step may run at the beginning or end of each workflow.

Do not delete today's file.

---

# 30. GitHub Actions Workflow

Create:

```text
.github/workflows/reward-code-bot.yml
```

It must:

1. Trigger on schedule.
2. Trigger manually with `workflow_dispatch`.
3. Checkout repository.
4. Setup Python.
5. Install dependencies.
6. Install Playwright Chromium.
7. Run the bot.
8. Commit/push changed daily data.
9. Upload debug artifacts when enabled.

The workflow should not run continuously all day.

Each scheduled execution should be a separate job.

---

# 31. Workflow Schedule

Target execution times:

```text
18:35
19:35
20:35
21:35
```

Vietnam timezone.

The +5-minute delay is intentional.

---

# 32. POC Phase — Mandatory

Do NOT implement the complete bot first.

Phase 1 must only prove:

```text
GitHub Actions
    |
    v
Chromium
    |
    v
TikTok profile
    |
    v
Detect LIVE
    |
    v
Enter LIVE
    |
    v
Take screenshot
    |
    v
Upload screenshot as GitHub Artifact
```

No OCR.

No Telegram.

No daily storage yet.

Expected artifact:

```text
live-screenshot.png
```

The POC is successful only if the screenshot actually contains the rendered livestream.

If TikTok cannot be rendered on GitHub Actions, stop and investigate before implementing the remaining phases.

---

# 33. Phase 2 — OCR

After Phase 1 succeeds:

```text
Screenshot
    |
    v
Crop Region A
    |
    v
OCR Small Code

Screenshot
    |
    v
Crop Region B
    |
    v
OCR Large Code
```

Print results in GitHub Actions logs:

```text
[OCR]
Small code: W3QG8MZ5
Large code: CODE GIỚI HẠN
```

After release:

```text
[OCR]
Small code: W3QG8MZ5
Large code: R5XJV9VQ2

[VALIDATION]
Large code confirmed.
```

---

# 34. Phase 3 — Storage

Add:

```text
data/YYYY-MM-DD.txt
```

Test:

```text
Run 1 -> save code
Run 2 -> same code -> skip
Run 3 -> new code -> save
```

Confirm persistence between separate GitHub Actions runs.

---

# 35. Phase 4 — Telegram

Add Telegram integration.

Test:

```text
new code
    |
    +--> save TXT
    |
    +--> send Telegram
```

Telegram failure must not cause code loss.

---

# 36. Phase 5 — Scheduler

After manual execution works:

Add scheduled execution:

```text
18:35
19:35
20:35
21:35
```

Keep:

```text
workflow_dispatch
```

for manual testing.

---

# 37. Phase 6 — Cleanup and Hardening

Add:

- cleanup of previous-day files;
- retry logic;
- structured logging;
- timeout handling;
- Git push conflict handling;
- OCR confidence/validation improvements;
- tests;
- README documentation.

---

# 38. Debug Mode

Support:

```text
DEBUG=true
```

When enabled, save:

```text
debug/
├── full.png
├── small_region.png
├── large_region.png
└── ocr.txt
```

Upload them as GitHub Actions artifacts.

Do not commit debug files.

---

# 39. Error Handling

Handle gracefully:

### TikTok cannot open

Retry.

### Profile cannot load

Retry.

### No LIVE

Check every 10 seconds for up to 5 minutes.

### LIVE does not render

Wait and retry screenshots.

### OCR fails

Continue with next frame.

### OCR gives inconsistent results

Do not send the code.

### Telegram fails

Save code anyway and log the failure.

### Git push conflict

Use safe pull/rebase/retry logic.

### Unexpected browser exception

Close browser cleanly and produce useful logs.

---

# 40. Security Requirements

`.gitignore` must exclude:

```text
.env
*.log
debug/
screenshots/*
__pycache__/
.pytest_cache/
.playwright/
```

Never commit:

- Telegram bot token;
- Telegram chat ID if considered sensitive;
- TikTok passwords;
- TikTok session cookies;
- browser profiles;
- authentication state;
- private credentials.

Do not attempt to bypass TikTok security mechanisms.

---

# 41. Tests

Create unit tests.

## `tests/test_validator.py`

Test examples:

```text
R5XJV9VQ2 -> valid
CODE GIỚI HẠN -> invalid
empty -> invalid
normal UI text -> invalid
```

## `tests/test_duplicate_checker.py`

Test:

```text
new code -> false
existing code -> true
```

## `tests/test_daily_file.py`

Test:

```text
create today's file
write code
read code
detect duplicate
```

## `tests/test_ocr.py`

Use the two supplied reference images:

```text
chua_code_lon.png
co_code_lon.png
```

Expected behavior:

```text
chua_code_lon.png
-> large code = NOT_RELEASED
```

and:

```text
co_code_lon.png
-> large code = actual large code
```

The exact OCR output must be verified against the actual image content during implementation.

---

# 42. README Requirements

README must document:

## Project purpose

Explain the bot.

## Local installation

```text
git clone ...
pip install -r requirements.txt
playwright install chromium
```

## Local test

```text
python -m app.main
```

## GitHub Secrets

Navigate to:

```text
Repository
-> Settings
-> Secrets and variables
-> Actions
```

Add:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

## Manual execution

```text
Actions
-> Reward Code Bot
-> Run workflow
```

## Schedule

Explain:

```text
18:35
19:35
20:35
21:35
Vietnam time
```

---

# 43. Definition of Done

The project is complete only when all are true:

```text
[ ] Opens the correct TikTok publisher profile
[ ] Does not depend on a fixed daily LIVE URL
[ ] Detects current LIVE
[ ] Opens current LIVE
[ ] Runs on GitHub Actions
[ ] Does not require BAT
[ ] Does not require a local PC to stay on
[ ] Runs at 18:35 / 19:35 / 20:35 / 21:35
[ ] Has retry when LIVE is not immediately visible
[ ] Takes screenshots
[ ] Detects small code
[ ] Detects large code
[ ] Recognizes "CODE GIỚI HẠN" as not released
[ ] Uses multi-frame confirmation
[ ] Validates OCR result
[ ] Creates daily TXT
[ ] Filters duplicate codes
[ ] Sends new codes through Telegram
[ ] Persists daily TXT between GitHub Actions runs
[ ] Cleans old daily files
[ ] Supports manual workflow_dispatch
[ ] Supports debug artifacts
[ ] Has unit tests
[ ] Has README
[ ] Contains no secrets
```

---

# 44. Mandatory Development Order

Follow this order strictly:

```text
PHASE 1
TikTok + Playwright + GitHub Actions
        |
        v
VERIFY LIVE ACCESS
        |
        v
PHASE 2
Screenshot + OCR
        |
        v
VERIFY OCR
        |
        v
PHASE 3
Daily TXT + Duplicate Detection
        |
        v
VERIFY STORAGE
        |
        v
PHASE 4
Telegram
        |
        v
VERIFY NOTIFICATION
        |
        v
PHASE 5
Scheduler
        |
        v
PHASE 6
Cleanup + Hardening + Tests
```

Do not skip Phase 1.

Do not implement the entire project before verifying that GitHub Actions Chromium can actually render the TikTok LIVE.

---

# 45. Important Engineering Note

The biggest technical risk is not Python, OCR, storage, or Telegram.

The biggest risk is:

```text
Can Chromium running on a GitHub-hosted runner
reliably open and render the TikTok LIVE?
```

Therefore Phase 1 is mandatory.

If TikTok LIVE does not render reliably in GitHub Actions, stop and report the exact failure before continuing.

Do not attempt to bypass CAPTCHA, anti-bot systems, login verification, or other platform security controls.

The rest of the architecture should remain modular so that the browser/runner component can later be replaced without rewriting OCR, storage, duplicate filtering, or Telegram modules.

---

# 46. Initial Deliverable

The first deliverable must be only the Phase 1 POC:

```text
.github/workflows/reward-code-bot.yml
app/
  tiktok/
    browser.py
    profile.py
    live_detector.py
    live_session.py
requirements.txt
README.md
.gitignore
```

The workflow must:

1. Start Chromium.
2. Open the publisher profile.
3. Detect whether it is LIVE.
4. Find the current LIVE.
5. Enter it.
6. Wait for rendering.
7. Take a screenshot.
8. Upload the screenshot as an artifact.
9. Exit cleanly.

After Phase 1 is verified, proceed to Phase 2.

