"""Ask for search options when a run starts."""

from __future__ import annotations

import re

from jobagent.posted import normalize_window


def parse_applicants(text) -> tuple[int, int]:
    """Return (min, max). Blank means no bound (keep all counts)."""
    raw = "" if text is None else str(text).strip().lower()
    if not raw:
        return (0, 0)
    raw = raw.replace("to", "-")
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", raw)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    if re.fullmatch(r"\d+", raw):
        return (0, int(raw))
    return (0, 0)


def parse_posted(text) -> str:
    """Blank means all time; otherwise a posted-window label."""
    if text is None or not str(text).strip():
        return "all"
    return normalize_window(text)


def run_options_from_answers(answers: dict) -> dict:
    keywords = str((answers or {}).get("keywords") or "").strip()
    location = str((answers or {}).get("location") or "").strip()
    if not keywords:
        raise ValueError("keywords are required")
    if not location:
        raise ValueError("location is required")
    min_n, max_n = parse_applicants((answers or {}).get("applicants"))
    return {
        "keywords": keywords,
        "location": location,
        "work_style": "remote",
        "min_applicants": min_n,
        "max_applicants": max_n,
        "posted_within": parse_posted((answers or {}).get("posted")),
    }


def apply_run_options(rules: dict, options: dict) -> dict:
    """Copy of rules with this-run location, remote work style, applicants, posted."""
    merged = dict(rules or {})
    options = options or {}
    if options.get("location"):
        merged["linkedin_location"] = options["location"]
    merged["work_style"] = options.get("work_style") or "remote"
    if "min_applicants" in options:
        merged["min_applicants"] = options["min_applicants"]
    if "max_applicants" in options:
        merged["max_applicants"] = options["max_applicants"]
    if options.get("posted_within") is not None:
        merged["posted_within"] = options["posted_within"]
    return merged


def resolve_run_options(args, input_fn=input) -> dict:
    """Use CLI flags when present; ask only for missing required fields."""
    keywords = str(getattr(args, "keywords", None) or "").strip()
    location = str(getattr(args, "location", None) or "").strip()
    posted = getattr(args, "time_filter", None)
    applicants = getattr(args, "applicants", None)
    return prompt_run_options(
        input_fn=input_fn,
        keywords=keywords,
        location=location,
        applicants="" if applicants is None else applicants,
        posted="" if posted is None else posted,
        ask_optional=not (keywords and location),
    )


def prompt_run_options(
    input_fn=input,
    keywords: str = "",
    location: str = "",
    applicants: str = "",
    posted: str = "",
    ask_optional: bool = True,
) -> dict:
    """Ask keywords, location, applicants, posted. Work style is always remote."""
    keywords = str(keywords or "").strip() or _ask_required(input_fn, "Search keywords: ")
    location = str(location or "").strip() or _ask_required(
        input_fn, "Countries or location: "
    )
    if ask_optional:
        if applicants is None or str(applicants).strip() == "":
            applicants = input_fn("Applicants (Enter = all): ")
        if posted is None or str(posted).strip() == "":
            posted = input_fn("Posted (Enter = all, or 2h/24h/7day): ")
    return run_options_from_answers(
        {
            "keywords": keywords,
            "location": location,
            "applicants": applicants,
            "posted": posted,
        }
    )


def _ask_required(input_fn, prompt: str) -> str:
    while True:
        value = str(input_fn(prompt) or "").strip()
        if value:
            return value
