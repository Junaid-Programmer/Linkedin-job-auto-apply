from __future__ import annotations

from jobagent.applicants import job_applicant_count
from jobagent.insights import keep_jobs_with_insights
from jobagent.posted import posted_within
from jobagent.ui_filters import applicant_allowed, parse_ui_filters, title_matches


def run_ready(status: dict) -> tuple[bool, str]:
    if not status.get("linkedin"):
        return False, "Connect LinkedIn"
    if not status.get("google"):
        return False, "Sign in with Google"
    if not str(status.get("spreadsheet_id") or "").strip() or not str(
        status.get("tab_name") or ""
    ).strip():
        return False, "Pick a spreadsheet and tab"
    if not str(status.get("keywords") or "").strip():
        return False, "Title keywords are required"
    if not str(status.get("country") or "").strip():
        return False, "Country is required"
    return True, ""


def filter_scraped_jobs(jobs: list[dict], filters: dict) -> list[dict]:
    keywords = filters.get("keywords") or ""
    posted = filters.get("posted") or "all"
    max_n = filters.get("max_applicants", 999)
    kept = []
    for job in keep_jobs_with_insights(jobs):
        if not title_matches(str(job.get("title") or ""), keywords):
            continue
        if not posted_within(job.get("posted"), posted):
            continue
        if not applicant_allowed(job_applicant_count(job), max_n):
            continue
        kept.append(job)
    return kept


def execute_ui_run(status: dict, payload: dict, scrape_fn, upsert_fn) -> dict:
    ok, reason = run_ready(status)
    if not ok:
        return {"ok": False, "status": "failed", "reason": reason, "scraped": 0}
    filters = parse_ui_filters(payload)
    try:
        jobs = scrape_fn(filters)
    except Exception as exc:
        return {"ok": False, "status": "failed", "reason": str(exc), "scraped": 0}
    kept = filter_scraped_jobs(jobs, filters)
    if not kept:
        return {"ok": True, "status": "done", "reason": "", "scraped": 0}
    try:
        upsert_fn(kept)
    except Exception as exc:
        return {"ok": False, "status": "failed", "reason": str(exc), "scraped": 0}
    return {"ok": True, "status": "done", "reason": "", "scraped": len(kept)}
