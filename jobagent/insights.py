"""Require posted time and applicant count on every scraped job."""

from __future__ import annotations

import re

from jobagent.applicants import parse_applicant_count

POSTED_LINE_RE = re.compile(
    r"^(reposted\s+)?(just now|today|yesterday|a (minute|hour|day|week|month) ago|"
    r"(\d+)\s*(m|h|d|w)|(an? )?(\d+)?\s*(minute|hour|day|week|month)s? ago)$",
    re.IGNORECASE,
)

POSTED_FRAGMENT_RE = re.compile(
    r"(?:reposted\s+)?(?:just now|\btoday\b|\byesterday\b|"
    r"an? (?:minute|hour|day|week|month) ago|"
    r"\d+\s*(?:minutes?|hours?|days?|weeks?|months?) ago|"
    r"\b\d+\s*(?:m|h|d|w)\b)",
    re.IGNORECASE,
)


def posted_line_from_text(text) -> str:
    """Return LinkedIn posted-time text, or empty if none is present."""
    if text is None:
        return ""
    try:
        blob = str(text).replace("\xa0", " ")
    except Exception:
        return ""
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        if POSTED_LINE_RE.match(line):
            return line
        match = POSTED_FRAGMENT_RE.search(line)
        if match:
            return match.group(0).strip()
    return ""


def has_required_insights(job: dict) -> bool:
    """True only when posted time and a numeric applicant count are both set."""
    if not isinstance(job, dict):
        return False
    posted = str(job.get("posted") or "").strip()
    if not posted:
        return False
    applicants = job.get("applicants")
    if applicants is None or applicants == "":
        return False
    if str(applicants).strip().lower() == "unknown":
        return False
    parsed = parse_applicant_count(applicants)
    if parsed is not None:
        return True
    try:
        int(str(applicants).replace(",", "").strip())
        return True
    except (TypeError, ValueError):
        return False


def keep_jobs_with_insights(jobs: list[dict]) -> list[dict]:
    """Drop jobs that still hide posted time or applicant count."""
    return [job for job in jobs if has_required_insights(job)]


def enrich_from_texts(job: dict, texts) -> dict:
    """Fill missing posted time and applicant count from UI strings."""
    if not isinstance(job, dict):
        return job
    if not str(job.get("posted") or "").strip():
        for raw in texts or []:
            posted = posted_line_from_text(raw)
            if posted:
                job["posted"] = posted
                break
    if not has_required_insights({**job, "posted": job.get("posted") or "placeholder"}):
        for raw in texts or []:
            parsed = parse_applicant_count(raw)
            if parsed is not None:
                job["applicants"] = parsed
                break
    return job


def jobs_needing_detail(jobs: dict) -> list[str]:
    """Ids that still need the detail pane: missing description or insights."""
    needed = []
    for job_id, job in jobs.items():
        description = ""
        if isinstance(job, dict):
            description = str(job.get("description") or "").strip()
        if not description or not has_required_insights(job):
            needed.append(job_id)
    return needed
