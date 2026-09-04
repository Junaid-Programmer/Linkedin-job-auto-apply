"""End-to-end orchestration: scrape -> sheet -> score -> tailor/skip."""

from __future__ import annotations

from pathlib import Path

from jobagent.config import Config, ConfigError
from jobagent.linkedin import (
    LinkedInScraper,
    LinkedInSession,
    load_jobs,
    save_jobs,
)
from jobagent.llm import LLMClient, LLMError
from jobagent.rules import evaluate as evaluate_rules, load_rules
from jobagent.scoring import keyword_score, score_job
from jobagent.sheets import JobSheet
from jobagent.tailor import prepare_application_package, prepare_application_package_fallback


class JobAgent:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.llm: LLMClient | None = None

    # ------------------------------------------------------------------
    # LLM (lazy, so scraping works even before a key is configured)
    # ------------------------------------------------------------------
    def get_llm(self) -> LLMClient:
        if self.llm is None:
            self.config.require_llm()
            self.llm = LLMClient(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
                model=self.config.llm_model,
            )
        return self.llm

    def load_profile(self) -> str:
        return _read_or_raise(
            Path(self.config.extra["profile_file"]),
            "profile.md",
            "Put your professional profile in profile.md (copy from profile.md.example).",
        )

    def load_resume(self) -> str:
        return _read_or_raise(
            Path(self.config.extra["resume_file"]),
            "resume.md",
            "Put your base resume in resume.md (copy from resume.md.example).",
        )

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------
    def scrape(
        self,
        keywords: str | None = None,
        location: str | None = None,
        pages: int | None = None,
        time_filter: str | None = None,
        save_to: str | None = None,
        headless: bool = True,
    ) -> list[dict]:
        keywords = keywords or self.config.search_keywords
        rules = load_rules(self.config.extra.get("rules_file", "rules.yaml"))
        rules_location = rules.get("linkedin_location")
        location = location or rules_location or self.config.search_location
        pages = pages or self.config.search_pages
        time_filter = self.config.search_time_filter if time_filter is None else time_filter
        save_to = save_to or self.config.extra["scraped_jobs_file"]

        session = LinkedInSession(self.config.state_file, headless=headless)
        session.start()
        try:
            if not session.logged_in:
                raise ConfigError(
                    "Not logged in to LinkedIn. Run `python run.py login` once "
                    "to save your session."
                )
            scraper = LinkedInScraper(session)
            jobs = scraper.scrape_search(
                keywords=keywords,
                location=location,
                max_pages=pages,
                time_filter=time_filter,
            )
        finally:
            session.close()
        save_jobs(jobs, save_to)
        return jobs

    def push_to_sheet(self, jobs: list[dict]) -> tuple[int, int]:
        self.config.require_sheets()
        sheet = JobSheet(
            self.config.google_service_account_file,
            self.config.google_sheet_name,
            self.config.google_sheet_id,
        )
        added, skipped = sheet.upsert_jobs(jobs)
        print(f"[sheets] added {added} new jobs, {skipped} already tracked")
        return added, skipped

    def score_pending(self) -> tuple[int, int]:
        """Score all unscored rows (after the rules gate). Returns
        (scored, skipped_below_threshold)."""
        self.config.require_sheets()
        profile = self.load_profile()
        llm = self.get_llm() if self.config.has_llm() else None
        if llm is None:
            print("[score] no LLM key configured - using offline keyword scoring")

        sheet = JobSheet(
            self.config.google_service_account_file,
            self.config.google_sheet_name,
            self.config.google_sheet_id,
        )
        pending = sheet.get_unscored()
        print(f"[score] {len(pending)} jobs waiting to be scored")
        rules = load_rules(self.config.extra.get("rules_file", "rules.yaml"))
        scored_count = 0
        skipped_low = 0
        skipped_rules = 0
        for row in pending:
            job = {
                "id": row.get("Job ID"),
                "title": row.get("Title"),
                "company": row.get("Company"),
                "location": row.get("Location"),
                "posted": row.get("Posted"),
                "url": row.get("LinkedIn URL"),
                "description": row.get("Description"),
            }
            decision = evaluate_rules(job, rules)
            if not decision["ok"]:
                reason = f"RULE: {decision['reason']}"
                sheet.update_score(job["id"], 0, reason)
                sheet.update_status(job["id"], "SKIPPED")
                skipped_rules += 1
                print(f"[score] {job['id']} {reason} -> SKIPPED")
                continue
            try:
                if llm is not None:
                    result = score_job(llm, job, profile)
                else:
                    result = keyword_score(job, profile)
            except LLMError as exc:
                print(f"[score] failed for {job['id']}: {exc}")
                continue
            score, reasons = result["score"], result["reasons"]
            sheet.update_score(job["id"], score, reasons)
            scored_count += 1
            if score < self.config.score_threshold:
                skipped_low += 1
                sheet.update_status(job["id"], "SKIPPED")
                print(f"[score] {job['id']} score={score} -> SKIPPED")
            else:
                print(f"[score] {job['id']} score={score} -> TARGET")
        print(
            f"[score] scored {scored_count} jobs, {skipped_low} below threshold, "
            f"{skipped_rules} blocked by rules"
        )
        return scored_count, skipped_low

    def tailor_targets(self) -> int:
        """Prepare application packages for scored, non-skipped jobs that
        do not have a package yet. Returns the number of packages made."""
        self.config.require_sheets()
        profile = self.load_profile()
        resume = self.load_resume()
        llm = self.get_llm() if self.config.has_llm() else None
        if llm is None:
            print("[tailor] no LLM key configured - using offline resume prep")

        sheet = JobSheet(
            self.config.google_service_account_file,
            self.config.google_sheet_name,
            self.config.google_sheet_id,
        )
        rows = sheet.worksheet().get_all_records()
        targets = [
            r
            for r in rows
            if _as_float(r.get("Score")) is not None
            and _as_float(r.get("Score")) >= self.config.score_threshold
            and str(r.get("Status", "")).strip() not in ("APPLY_READY",)
        ]
        print(f"[tailor] {len(targets)} jobs to tailor for")
        made = 0
        for row in targets:
            job = {
                "id": row.get("Job ID"),
                "title": row.get("Title"),
                "company": row.get("Company"),
                "location": row.get("Location"),
                "url": row.get("LinkedIn URL"),
                "description": row.get("Description"),
            }
            try:
                if llm is not None:
                    package = prepare_application_package(
                        llm, job, resume, profile, self.config.extra["output_dir"]
                    )
                else:
                    package = prepare_application_package_fallback(
                        job, resume, profile, self.config.extra["output_dir"]
                    )
            except LLMError as exc:
                print(f"[tailor] failed for {job['id']}: {exc}")
                continue
            sheet.update_status(job["id"], "APPLY_READY", package)
            made += 1
            print(f"[tailor] {job['id']} -> {package}")
        return made

    def enforce_rules(self) -> tuple[int, int]:
        """Re-check every already-scored row against the current rules and
        skip any that now fail (e.g. after tightening the location filter).
        Returns (blocked, still_ok)."""
        self.config.require_sheets()
        sheet = JobSheet(
            self.config.google_service_account_file,
            self.config.google_sheet_name,
            self.config.google_sheet_id,
        )
        rules = load_rules(self.config.extra.get("rules_file", "rules.yaml"))
        rows = sheet.worksheet().get_all_records()
        blocked = 0
        ok = 0
        for row in rows:
            if _as_float(row.get("Score")) is None:
                continue
            if str(row.get("Status", "")).strip() == "SKIPPED":
                continue
            job = {
                "id": row.get("Job ID"),
                "title": row.get("Title"),
                "company": row.get("Company"),
                "location": row.get("Location"),
                "posted": row.get("Posted"),
                "url": row.get("LinkedIn URL"),
                "description": row.get("Description"),
            }
            decision = evaluate_rules(job, rules)
            if not decision["ok"]:
                sheet.update_score(job["id"], 0, f"RULE: {decision['reason']}")
                sheet.update_status(job["id"], "SKIPPED")
                blocked += 1
                print(f"[rules] {job['id']} {decision['reason']} -> SKIPPED")
            else:
                ok += 1
        print(f"[rules] {blocked} jobs now blocked, {ok} still passing")
        return blocked, ok

    def run(
        self,
        keywords: str | None = None,
        location: str | None = None,
        pages: int | None = None,
    ) -> None:
        """Full pipeline: scrape -> sheet -> score -> tailor/skip."""
        print("== scraping LinkedIn ==")
        jobs = self.scrape(keywords=keywords, location=location, pages=pages)
        if not jobs:
            print("No jobs found.")
            return
        print("== pushing to Google Sheets ==")
        self.push_to_sheet(jobs)
        print("== scoring ==")
        try:
            self.score_pending()
        except (ConfigError, LLMError) as exc:
            print(f"[run] scoring skipped: {exc}")
            return
        print("== tailoring ==")
        try:
            self.tailor_targets()
        except ConfigError as exc:
            print(f"[run] tailoring skipped: {exc}")
        print("== done ==")


def _read_or_raise(path: Path, name: str, hint: str) -> str:
    if not path.exists():
        raise ConfigError(f"Missing {name}. {hint}")
    return path.read_text(encoding="utf-8")


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
