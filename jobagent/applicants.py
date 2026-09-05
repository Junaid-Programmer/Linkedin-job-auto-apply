"""Parse LinkedIn applicant-count text and apply min/max filters."""

from __future__ import annotations

import re


def parse_applicant_count(text) -> int | None:
    """Pull the number of people who already applied from LinkedIn text.

    Handles "23 applicants", "Over 100 applicants", "100+", and
    "Be among the first 25 applicants". Returns None when no count is found.
    """
    if text is None:
        return None
    try:
        cleaned = str(text).replace(",", "").replace("\xa0", " ").strip()
    except Exception:
        return None
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if "applicant" not in lowered and "applied" not in lowered and "clicked apply" not in lowered:
        return None
    over = re.search(r"(?:over|more than)\s+(\d+)", lowered)
    if over:
        return int(over.group(1))
    plus = re.search(r"(\d+)\s*\+", lowered)
    if plus:
        return int(plus.group(1))
    first = re.search(r"be among the first\s+(\d+)", lowered)
    if first:
        return int(first.group(1))
    plain = re.search(r"(\d+)\s*(?:applicant|people clicked apply|people applied)", lowered)
    if plain:
        return int(plain.group(1))
    return None


def applicant_count_allowed(count, min_applicants: int = 0, max_applicants: int = 0) -> bool:
    """True when `count` passes min/max. 0 means that bound is unused.

    Unknown counts fail only when at least one bound is set.
    """
    try:
        min_n = int(min_applicants or 0)
        max_n = int(max_applicants or 0)
    except (TypeError, ValueError):
        min_n, max_n = 0, 0
    if min_n <= 0 and max_n <= 0:
        return True
    if count is None or count == "" or str(count).strip().lower() == "unknown":
        return False
    try:
        n = int(count)
    except (TypeError, ValueError):
        return False
    if min_n > 0 and n < min_n:
        return False
    if max_n > 0 and n > max_n:
        return False
    return True


def job_applicant_count(job: dict):
    """Read an applicant count from a scraped job or a sheet row."""
    if not isinstance(job, dict):
        return None
    for key in (
        "applicants",
        "applicant_count",
        "applications_submitted",
        "Applications Submitted",
    ):
        raw = job.get(key)
        if raw in (None, "", "Unknown"):
            continue
        parsed = parse_applicant_count(raw)
        if parsed is not None:
            return parsed
        try:
            return int(str(raw).replace(",", "").strip())
        except (TypeError, ValueError):
            continue
    for key in ("insight", "posted"):
        parsed = parse_applicant_count(job.get(key))
        if parsed is not None:
            return parsed
    return None
