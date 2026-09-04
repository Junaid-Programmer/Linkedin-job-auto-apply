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
python run.py run

# With custom search
python run.py run --keywords "senior python developer" --location "Berlin" --pages 3

# Individual steps
python run.py scrape --keywords "fastapi" --pages 2   # scrape only
python run.py score                                    # score unscored rows
python run.py enforce                                  # re-check scored rows against rules.yaml
python run.py tailor                                   # prepare packages for targets
```

## Where the rules live: `rules.yaml`

The **rules gate** runs before scoring. Any job that fails a rule is marked
`SKIPPED` in the sheet with the reason in the **Match Reasons** column, and is
never scored or tailored. Edit `rules.yaml` to control it — every section is
commented and you can turn a rule off by emptying its list.

```yaml
# Location sent to LinkedIn search (overrides LINKEDIN_SEARCH_LOCATION)
linkedin_location: Europe

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
work_style: any             # any | remote only | on-site only | hybrid only
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
   search for your keywords, walks the result pages at a human-like pace, reads
   the full description of each listing, and saves to `data/scraped_jobs.json`.
2. **Sheet** (`jobagent/sheets.py`): new jobs are appended to the spreadsheet,
   deduplicated by LinkedIn job ID.
3. **Rules gate** (`jobagent/rules.py` + `rules.yaml`): every job is checked
   against your rules before scoring — country of the employer's location,
   company blocklist, required/excluded keywords, work style. Failures are
   marked `SKIPPED` with a reason.
4. **Score** (`jobagent/scoring.py`): each remaining unscored row is sent to
   the LLM with your profile; it returns a 0–100 score and reasons.
   `>= SCORE_THRESHOLD` becomes a target, otherwise `SKIPPED`.
5. **Tailor** (`jobagent/tailor.py`): for each target, the LLM rewrites your
   resume to match the posting (honestly — no invented facts) and writes a
   short application note into `output/tailored/<company>-<title>/`.

## Google Sheet columns

`Timestamp | Job ID | Title | Company | Location | Posted | LinkedIn URL | Description | Score | Match Reasons | Status | Apply Package`

Status values: `NEW` → scored → `TARGET` / `SKIPPED` → `APPLY_READY` (with the
path to the generated package).
