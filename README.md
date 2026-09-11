# LinkedIn Job Agent

An agent that scrapes job listings from LinkedIn search pages, stores them in a
Google Sheet, **filters them through your own rules** (e.g. "only companies in
Europe"), scores each one against **your** profile with an LLM, and prepares
a tailored resume + cover note for the jobs that match well. Low-scoring jobs
are skipped automatically.

```
scrape  →  Google Sheet  →  rules gate (region/company/keywords)
                              ↓ pass                  ↓ fail
                       score vs profile           SKIPPED (with reason)
                              ↓ >= threshold
                        tailor resume / skip
```

## What it does NOT do

- It does **not** click "Apply" on LinkedIn for you. Automated applications
  violate LinkedIn's Terms of Service and are the fastest way to get an account
  banned. The agent prepares everything (tailored resume + application note in
  `output/tailored/<company>-<title>/`) and you submit it yourself with one
  click.
- It only **reads** public job listings from LinkedIn with your own logged-in
  session. Scraping still technically conflicts with LinkedIn's ToS, so use the
  tools at a gentle pace (built-in delays) and at your own risk.

## Local control page (Windows)

Clone the repo, then run two commands:

```bat
setup.bat
run-ui.bat
```

`setup.bat` creates `.venv`, installs requirements, and installs Playwright Chromium.
`run-ui.bat` runs `python run.py ui`, which starts a local page at `http://127.0.0.1:8765` and opens the default browser.

On that page:

1. Copy `google_oauth_client.json.example` to `google_oauth_client.json` and fill in the Desktop OAuth client (the project owner may commit the real file).
2. Click **Connect LinkedIn**. Log in by hand; the session is saved to `data/linkedin_state.json`.
3. Click **Sign in with Google**. Tokens are saved to `data/google_token.json`.
4. Pick a spreadsheet, then a tab.
5. Fill title keywords and country, then click **Run**.

This page does **not** click Apply. Jobs are written to the chosen Sheet tab. You apply by hand.

`python run.py watch` is unchanged (Sheet Control tab).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 1. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | What to put |
|---|---|
| `USER_LLM_API_KEY` | **Your own** API key (DeepSeek, OpenAI, OpenRouter, any `/chat/completions` provider). The code never reads keys from anywhere else. |
| `USER_LLM_BASE_URL` / `USER_LLM_MODEL` | Endpoint + model (defaults: DeepSeek). |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to your Google service-account JSON. |
| `GOOGLE_SHEET_NAME` | Spreadsheet name (created automatically). |
| `SCORE_THRESHOLD` | Match score cutoff. Jobs below it are skipped. |
| `LINKEDIN_SEARCH_*` | Default search keywords / location / pages / time filter. |

### 2. Google Sheets access

1. Go to https://console.cloud.google.com → create a project.
2. Enable the **Google Sheets API**.
3. Create a **Service Account**, download its JSON key to `data/service_account.json`.
4. Create a spreadsheet in Google Sheets, share it (Editor) with the service
   account's email address (found inside the JSON, field `client_email`).

### 3. Your profile and resume

```bash
cp profile.md.example profile.md
cp resume.md.example resume.md
```

Edit `profile.md` (used for scoring) and `resume.md` (base resume, used for
tailoring).

### 4. LinkedIn session (one time)

On a machine with a display (your own computer):

```bash
python run.py login --manual
```

A browser opens; log in to LinkedIn. When it says session saved, upload the
single file `data/linkedin_state.json` to this project's `data/` folder (or run
the login here directly and paste your credentials when prompted with
`python run.py login`).

## Usage

```bash
# Full pipeline: scrape -> sheet -> score -> tailor/skip
# Asks for keywords and location. Work style is always Remote.
# Applicants and posted: press Enter to keep all.
python run.py run

# Skip the prompts with flags
python run.py run --keywords "senior python developer" --location "Berlin" --pages 3 --posted 24h

# Individual steps
python run.py scrape --keywords "fastapi" --pages 2   # scrape only
python run.py score                                    # score unscored rows
python run.py enforce                                  # re-check scored rows against rules.yaml
python run.py tailor                                   # prepare packages for targets

# Watch the Sheet Control tab (no keyword prompts)
python run.py watch

# Local control page (does not click Apply)
python run.py ui
```

## Control tab

The spreadsheet has a **Control** tab. Fill the filters, tick Start, and keep
`python run.py watch` running on your PC. It polls about every 10 seconds,
scrapes LinkedIn into the jobs sheet, then unticks Start. It does not score,
tailor, or click Apply — apply by hand.

| Column | What to put |
|---|---|
| Keywords | Search keywords (required) |
| Location | Search location (required) |
| Applicants | Max or min-max (e.g. `50` or `10-50`). Blank = all |
| Posted | `2h`, `5h`, `7h`, `24h`, `2day`, `7day`, or `all`. Blank = all |
| Start | Tick/TRUE to start a scrape |
| Status | Written by the watcher (`running`, then `done` or `error`) |

Work style is always Remote. It is not a Control field.

Fill Keywords + Location, tick Start. Status shows running then done. Apply by hand.

## Where the rules live: `rules.yaml`

The **rules gate** runs before scoring. Any job that fails a rule is marked
`SKIPPED` in the sheet with the reason in the **Match Reasons** column, and is
never scored or tailored. Edit `rules.yaml` to control it — every section is
commented and you can turn a rule off by emptying its list.

```yaml
# Location sent to LinkedIn search (overrides LINKEDIN_SEARCH_LOCATION)
linkedin_location: Europe

# Skip jobs that already have too many (or too few) applicants. 0 = unused.
min_applicants: 0
max_applicants: 50

# Keep jobs posted within this window: 2h | 5h | 7h | 24h | 2day | 7day | all
posted_within: 24h

# Job must be physically in one of these countries
allow_countries:
  - Germany
  - France
  # ... add any EU country; add "United Kingdom", "Switzerland" if you want them

# true  = accept a posting that just says "Remote" with no country
# false = reject any remote posting without a specific country
allow_remote_unknown: true

excluded_companies: []      # e.g. ["spam staffing"]
required_keywords: []       # posting must contain ALL of these
excluded_keywords: []       # posting containing ANY of these is rejected
work_style: any             # any | remote | remote only | hybrid | hybrid only | on-site | on-site only
employment_keywords: []     # e.g. ["full-time"] (any-of)
level_keywords: []          # e.g. ["junior", "entry level"] (any-of)
preferred_keywords: []      # not a gate; nudges the offline scorer
```

Some notes:

- Country matching also recognises region labels (`APAC`, `APJ`, `LATAM`,
  `MENA`, `North America`, ...) so a listing scoped to one of those is treated
  as not-Europe. `EMEA` is treated as unknown (it overlaps Europe).
- For on-site/hybrid jobs the country must appear in the Location field
  (e.g. `Berlin, Germany (Hybrid)`). Purely remote jobs have no country to
  check, so `allow_remote_unknown` decides their fate.
- After editing `allow_countries` or other rules, run
  `python run.py enforce` to re-check rows that were already scored and skip
  the ones that now fail.

## How it works

1. **Scrape** (`jobagent/linkedin.py`): Playwright opens the LinkedIn job
   search for your keywords, walks the result pages at a human-like pace, opens
   every listing to read posted time, applicant count, and the full description,
   and saves to `data/scraped_jobs.json`. Jobs that still hide posted time or
   applicant count are skipped.
2. **Sheet** (`jobagent/sheets.py`): new jobs are appended to the spreadsheet,
   deduplicated by LinkedIn job ID.
3. **Rules gate** (`jobagent/rules.py` + `rules.yaml`): every job is checked
   against your rules before scoring — country of the employer's location,
    company blocklist, required/excluded keywords, work style, optional
    min/max applicant counts, and posted-time window (`2h`, `5h`, `7h`, `24h`,
    `2day`, `7day`, `all`). Missing posted time or a hidden applicant count is
    always skipped. Failures are marked `SKIPPED` with a reason.
4. **Score** (`jobagent/scoring.py`): each remaining unscored row is sent to
   the LLM with your profile; it returns a 0–100 score and reasons.
   `>= SCORE_THRESHOLD` becomes a target, otherwise `SKIPPED`.
5. **Tailor** (`jobagent/tailor.py`): for each target, the LLM rewrites your
   resume to match the posting (honestly — no invented facts) and writes a
   short application note into `output/tailored/<company>-<title>/`.

## Google Sheet columns

`Timestamp | Job ID | Title | Company | Location | Posted | LinkedIn URL | Description | Applications Submitted | Score | Match Reasons | Status | Apply Package`

The **Posted** column stores LinkedIn's posted text (e.g. `2 hours ago`).
Override the window with `--posted 2h` / `5h` / `7h` / `24h` / `2day` / `7day` / `all`,
or set `posted_within` in `rules.yaml`. LinkedIn search only has 24h / week / any,
so 2h, 5h, 7h, and 2day are tightened locally from that Posted text.

Status values: `NEW` → scored → `TARGET` / `SKIPPED` → `APPLY_READY` (with the
path to the generated package).
