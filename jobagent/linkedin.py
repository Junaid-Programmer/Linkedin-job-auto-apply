"""LinkedIn job search scraper built on Playwright.

Uses your own logged-in browser session (saved once by the `login`
command) to read public job search results. It scrapes at a gentle,
human-like pace and only reads job listings - it never posts or
applies to anything on your behalf.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    BrowserContext,
    Error,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

LINKEDIN_BASE = "https://www.linkedin.com"
JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")
POSTED_RE = re.compile(
    r"^(reposted\s+)?(just now|today|yesterday|a (minute|hour|day|week|month) ago|"
    r"(\d+)\s*(m|h|d|w)|(an? )?(\d+)?\s*(minute|hour|day|week|month)s? ago)$",
    re.IGNORECASE,
)

# Candidate CSS selectors, listed most-recent-first so a LinkedIn UI
# change only breaks the first entries, not the whole extractor.
TITLE_SELECTORS = [
    "a.job-card-list__title--link",
    "a.job-card-list__title",
    "a.jobs-search-result__link strong",
]
COMPANY_SELECTORS = [
    "div.artdeco-entity-lockup__subtitle span",
    "span.job-card-container__primary-description",
    "span.job-card-list__company-name",
    "a.job-card-container__company-name",
]
LOCATION_SELECTORS = [
    "ul.job-card-container__metadata-wrapper li span",
    "li.job-card-container__metadata-item",
    "span.job-card-container__metadata-item",
    "span.job-card-list__location",
]
DESCRIPTION_SELECTORS = [
    ".jobs-description-content__text",
    ".jobs-description__content",
    ".jobs-box__html-content",
    "#job-details",
]
LIST_ITEM_SELECTOR = "li.scaffold-layout__list-item"

# How long to pause between actions, to stay well below LinkedIn's
# aggressive-usage threshold.
MIN_DELAY_MS = 800
MAX_DELAY_MS = 1800


def _human_delay() -> None:
    time.sleep(random.uniform(MIN_DELAY_MS / 1000, MAX_DELAY_MS / 1000))


class LinkedInSession:
    """Manages a Chromium context backed by a single storage-state file.

    After the user logs in once, the session cookies are exported to
    `data/linkedin_state.json` (one portable file), so the same session
    can be uploaded and reused on another machine.
    """

    def __init__(self, state_file: str, headless: bool = True) -> None:
        self.state_file = state_file
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context: Optional[BrowserContext] = None

    def start(self) -> None:
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            state_path = Path(self.state_file)
            self._context = self._browser.new_context(
                storage_state=str(state_path) if state_path.exists() else None,
                viewport={"width": 1280, "height": 900},
            )
        except Error:
            # Headless Chromium may need the browser installed first.
            raise RuntimeError(
                "Could not launch Chromium. Run:  python -m playwright install chromium"
            )

    def close(self) -> None:
        if self._context:
            try:
                self._context.close()
            except Error:
                pass
            self._context = None
        if self._browser:
            try:
                self._browser.close()
            except Error:
                pass
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def save_state(self) -> None:
        """Export cookies to the single storage-state file."""
        if self._context:
            Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=self.state_file)

    @property
    def logged_in(self) -> bool:
        if not self._context:
            return False
        cookies = self._context.cookies()
        return any(c.get("name") == "li_at" and c.get("value") for c in cookies)

    def new_page(self) -> Page:
        assert self._context is not None
        return self._context.new_page()


def login_interactive(state_file: str) -> None:
    """Open a real browser so the user can log in, then save the session."""
    session = LinkedInSession(state_file, headless=False)
    session.start()
    page = session.new_page()
    print("A browser window is opening. Log in to LinkedIn manually.\n")
    page.goto(f"{LINKEDIN_BASE}/login", timeout=60000, wait_until="domcontentloaded")
    try:
        page.wait_for_timeout(2000)
    except PlaywrightTimeoutError:
        pass
    print("Waiting for login...")
    deadline = time.time() + 600
    while time.time() < deadline:
        if session.logged_in:
            break
        time.sleep(2)
    if not session.logged_in:
        print("Timed out waiting for login.")
        session.close()
        raise RuntimeError("Login did not complete in time.")
    page.goto(f"{LINKEDIN_BASE}/feed", timeout=60000, wait_until="domcontentloaded")
    session.save_state()
    print(f"Session saved to {state_file}")
    session.close()


def login_credentials(state_file: str, email: str, password: str) -> None:
    """Log in with email + password by filling the LinkedIn form directly.

    The password is used only to fill the form and is never stored or logged.
    Headless-mode login can trip LinkedIn's security checks; if that happens,
    fall back to `login_interactive` on a machine with a display.
    """
    session = LinkedInSession(state_file, headless=True)
    session.start()
    page = session.new_page()
    try:
        page.goto(f"{LINKEDIN_BASE}/login", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector("#username, input[name='session_key']", timeout=30000)
        page.fill("#username", email)
        page.fill("#password", password)
        try:
            page.click("button[type='submit']", timeout=5000)
        except (PlaywrightTimeoutError, Error):
            page.click(".btn__primary--large", timeout=5000)
        deadline = time.time() + 90
        while time.time() < deadline:
            if session.logged_in:
                break
            time.sleep(2)
        if not session.logged_in:
            raise RuntimeError(
                "LinkedIn did not accept the login (wrong credentials or a security "
                "check such as 2FA/CAPTCHA was triggered). Run `python run.py login` "
                "on a machine with a browser to complete it manually."
            )
        page.goto(f"{LINKEDIN_BASE}/feed", timeout=60000, wait_until="domcontentloaded")
        session.save_state()
        print(f"Logged in. Session saved to {state_file}")
    finally:
        session.close()


def _build_search_url(
    keywords: str, location: str, page_index: int, time_filter: str
) -> str:
    params = [
        f"keywords={quote(keywords)}",
        f"location={quote(location)}",
        f"start={page_index * 25}",
    ]
    if time_filter:
        params.append(f"f_TPR={time_filter}")
    return f"{LINKEDIN_BASE}/jobs/search/?{'&'.join(params)}"


def quote(value: str) -> str:
    from urllib.parse import quote as _quote

    return _quote(value)


class LinkedInScraper:
    def __init__(self, session: LinkedInSession) -> None:
        self.session = session

    def scrape_search(
        self,
        keywords: str,
        location: str,
        max_pages: int = 2,
        time_filter: str = "",
        max_jobs: Optional[int] = None,
    ) -> list[dict]:
        page = self.session.new_page()
        jobs: dict[str, dict] = {}
        try:
            for page_index in range(max_pages):
                if max_jobs and len(jobs) >= max_jobs:
                    break
                url = _build_search_url(keywords, location, page_index, time_filter)
                print(f"[scraper] page {page_index + 1}/{max_pages}: {url}")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                self._wait_for_results(page)
                found = self._extract_page(page, jobs)
                print(f"[scraper] {found} new jobs on page {page_index + 1}")
                if found == 0 and page_index > 0:
                    break
            return list(jobs.values())
        finally:
            page.close()

    def _wait_for_results(self, page: Page) -> None:
        try:
            page.wait_for_selector(
                f"{LIST_ITEM_SELECTOR}, div.jobs-search-results-list",
                timeout=45000,
            )
        except PlaywrightTimeoutError:
            if not self.session.logged_in:
                raise RuntimeError(
                    "Not logged in to LinkedIn (search results require a session). "
                    "Run:  python run.py login"
                )
            raise RuntimeError(
                "LinkedIn changed its markup or blocked this request. "
                "Take a screenshot at this URL in a normal browser to inspect."
            )
        _human_delay()

    def _extract_page(self, page: Page, jobs: dict[str, dict]) -> int:
        """Extract every job card on the current results page.

        Cards are collected, then each is opened to read the full job
        description from the detail pane.
        """
        cards = page.locator(LIST_ITEM_SELECTOR)
        card_count = cards.count()
        if card_count == 0:
            return 0

        found = 0
        for i in range(card_count):
            card = cards.nth(i)
            href = _first_text(card, TITLE_SELECTORS, attr="href")
            if not href:
                href = _first_text(card, ["a[href*='/jobs/view/']"], attr="href")
            if not href:
                continue
            match = JOB_ID_RE.search(href)
            job_id = match.group(1) if match else href
            if job_id in jobs:
                continue

            title = _first_text(card, TITLE_SELECTORS)
            company = _first_text(card, COMPANY_SELECTORS)
            location = _first_text(card, LOCATION_SELECTORS)
            posted = _extract_posted(card)
            applicants = _extract_applicants(card)
            jobs[job_id] = {
                "id": job_id,
                "title": title or "Unknown title",
                "company": company or "Unknown company",
                "location": location or "Unknown location",
                "posted": posted or "",
                "url": f"{LINKEDIN_BASE}/jobs/view/{job_id}",
                "description": "",
                "applicants": applicants,
            }
            found += 1

        # Read the description for each new card by opening it in the
        # detail pane. Only the first few to keep request volume low.
        new_ids = [jid for jid in jobs if not jobs[jid]["description"]]
        for jid in new_ids[:15]:
            self._read_description(page, jid, jobs)
        return found

    def _read_description(self, page: Page, job_id: str, jobs: dict[str, dict]) -> None:
        try:
            card = page.locator(
                f"a[href*='/jobs/view/{job_id}']"
            ).first
            card.click(timeout=8000)
        except (PlaywrightTimeoutError, Error):
            return
        _human_delay()

        # Expand collapsed descriptions when LinkedIn shows a
        # "View all job details" footer button.
        try:
            expand = page.locator(
                "button.jobs-description__footer-button, "
                "button[aria-label*='View all job details']"
            ).first
            if expand.is_visible():
                expand.click(timeout=3000)
                _human_delay()
        except (PlaywrightTimeoutError, Error):
            pass

        description = _first_text(page, DESCRIPTION_SELECTORS, default="")
        description = re.sub(r"\n{3,}", "\n\n", description).strip()
        if description:
            jobs[job_id]["description"] = description
        applicants = _extract_applicants(page)
        if applicants is not None:
            jobs[job_id]["applicants"] = applicants


def _extract_applicants(parent) -> int | None:
    """Read LinkedIn's 'X applicants' insight from a card or detail pane."""
    from jobagent.applicants import parse_applicant_count

    selectors = [
        ".jobs-unified-top-card__applicant-count",
        ".job-details-jobs-unified-top-card__applicant-count",
        ".jobs-details-top-card__applicant-count",
        ".tvm__text--neutral",
        "ul.job-card-container__metadata-wrapper li span",
        "li.job-card-container__metadata-item",
        "span.job-card-container__metadata-item",
        ".job-details-jobs-unified-top-card__tertiary-description-container",
        ".jobs-unified-top-card__tertiary-description-container",
    ]
    texts = []
    for selector in selectors:
        try:
            texts.extend(parent.locator(selector).all_inner_texts())
        except (PlaywrightTimeoutError, Error):
            continue
    for text in texts:
        count = parse_applicant_count(text)
        if count is not None:
            return count
    return None


def _extract_posted(card) -> str:
    """Look for a human-readable posted date ("2 days ago", "today"...)
    anywhere on the job card, ignoring status badges like Viewed/Promoted."""
    candidates = []
    try:
        candidates += card.locator("time").all_inner_texts()
        candidates += card.locator("ul.job-card-container__footer-wrapper li").all_inner_texts()
    except (PlaywrightTimeoutError, Error):
        pass
    for text in candidates:
        for line in text.splitlines():
            line = line.strip()
            if POSTED_RE.match(line):
                return line
    return ""


def _first_text(parent, selectors, attr: Optional[str] = None, default: str = "") -> str:
    """Return the text (or attribute) of the first matching element across
    a list of selector strings, tolerating empty or missing elements."""
    for selector in selectors:
        target = parent.locator(selector).first
        try:
            if target.count() == 0:
                continue
            if attr:
                value = target.get_attribute(attr) or ""
            else:
                value = target.inner_text()
            value = value.strip()
            if value:
                return value
        except (PlaywrightTimeoutError, Error):
            continue
    return default


def save_jobs(jobs: list[dict], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[scraper] saved {len(jobs)} jobs to {path}")


def load_jobs(path: str) -> list[dict]:
    if not Path(path).exists():
        return []
    return json.loads(Path(path).read_text(encoding="utf-8"))
