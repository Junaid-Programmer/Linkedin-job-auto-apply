"""Rule engine for hard job filters.

Reads `rules.yaml` and decides, before scoring, whether a job should be
kept at all. A job that fails any enabled rule is skipped (never scored
or tailored). All checks are case-insensitive substring / word matches.
"""

from __future__ import annotations

import re
from pathlib import Path

from jobagent.applicants import applicant_count_allowed, job_applicant_count
from jobagent.posted import posted_within

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

DEFAULT_RULES = {
    "linkedin_location": "",
    "allow_countries": [],
    "allow_remote_unknown": True,
    "excluded_companies": [],
    "required_keywords": [],
    "excluded_keywords": [],
    "work_style": "any",
    "employment_keywords": [],
    "level_keywords": [],
    "preferred_keywords": [],
    "min_applicants": 0,
    "max_applicants": 0,
    "posted_within": "all",
}

# alias -> canonical country name. Canonical names should match the
# values used in rules.yaml `allow_countries`.
_COUNTRY_ALIASES = {
    "austria": "Austria",
    "belgium": "Belgium",
    "bulgaria": "Bulgaria",
    "croatia": "Croatia",
    "cyprus": "Cyprus",
    "czechia": "Czechia",
    "czech republic": "Czechia",
    "denmark": "Denmark",
    "estonia": "Estonia",
    "finland": "Finland",
    "france": "France",
    "germany": "Germany",
    "greece": "Greece",
    "hungary": "Hungary",
    "ireland": "Ireland",
    "italy": "Italy",
    "latvia": "Latvia",
    "lithuania": "Lithuania",
    "luxembourg": "Luxembourg",
    "malta": "Malta",
    "netherlands": "Netherlands",
    "holland": "Netherlands",
    "poland": "Poland",
    "portugal": "Portugal",
    "romania": "Romania",
    "slovakia": "Slovakia",
    "slovenia": "Slovenia",
    "spain": "Spain",
    "sweden": "Sweden",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",
    "switzerland": "Switzerland",
    "norway": "Norway",
    "iceland": "Iceland",
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "pakistan": "Pakistan",
    "india": "India",
    "canada": "Canada",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "uae": "United Arab Emirates",
    "dubai": "United Arab Emirates",
    "saudi arabia": "Saudi Arabia",
    "qatar": "Qatar",
    "japan": "Japan",
    "china": "China",
    "hong kong": "Hong Kong",
    "south korea": "South Korea",
    "singapore": "Singapore",
    "brazil": "Brazil",
    "mexico": "Mexico",
    "egypt": "Egypt",
    "nigeria": "Nigeria",
    "kenya": "Kenya",
    "south africa": "South Africa",
    "ukraine": "Ukraine",
    "russia": "Russia",
    "turkey": "Turkey",
    "philippines": "Philippines",
    "indonesia": "Indonesia",
    "malaysia": "Malaysia",
    "thailand": "Thailand",
    "vietnam": "Vietnam",
    "bangladesh": "Bangladesh",
    "sri lanka": "Sri Lanka",
    "afghanistan": "Afghanistan",
    "argentina": "Argentina",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Peru",
    "europe": "Europe",
    "eu": "Europe",
    "apac": "Asia-Pacific",
    "apj": "Asia-Pacific",
    "asia pacific": "Asia-Pacific",
    "latam": "Latin America",
    "latin america": "Latin America",
    "mena": "Middle East & North Africa",
    "middle east": "Middle East",
    "north america": "North America",
}

# Sorted longest-first so multi-word aliases win over short ones.
_COUNTRY_ALIAS_ITEMS = sorted(
    _COUNTRY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True
)


def load_rules(path: str = "rules.yaml") -> dict:
    """Load rules from a YAML file, merging missing keys with defaults.
    Returns the defaults if the file is missing or unreadable."""
    if yaml is None:
        return dict(DEFAULT_RULES)
    rules_path = Path(path)
    if not rules_path.exists():
        return dict(DEFAULT_RULES)
    try:
        loaded = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return dict(DEFAULT_RULES)
    merged = dict(DEFAULT_RULES)
    for key, value in loaded.items():
        if key in merged and value is not None:
            merged[key] = value
    return merged


def _norm_text(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


def _alias_in_text(alias: str, text: str) -> bool:
    alias = alias.lower()
    if alias.isalpha() and len(alias) <= 3:
        return re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text) is not None
    return alias in text


def detect_country(text: str) -> str | None:
    """Return the canonical name of a country mentioned in `text`, or
    None when nothing recognizable is found."""
    lowered = _norm_text(text)
    for alias, country in _COUNTRY_ALIAS_ITEMS:
        if _alias_in_text(alias, lowered):
            return country
    return None


def _allowed_countries(rules: dict) -> set[str]:
    return {str(c).strip().lower() for c in rules.get("allow_countries", []) if str(c).strip()}


def _detect_work_style(job: dict) -> str | None:
    """remote / hybrid / on-site inferred from the location string."""
    loc = (job.get("location") or "").lower()
    if "remote" in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    if "on-site" in loc or "on site" in loc:
        return "on-site"
    return None


def evaluate(job: dict, rules: dict) -> dict:
    """Apply every enabled rule to a job.

    Returns {"ok": True} or {"ok": False, "reason": "..."}.
    """
    rules = rules or DEFAULT_RULES
    title = str(job.get("title") or "")
    company = str(job.get("company") or "")
    location = str(job.get("location") or "")
    description = str(job.get("description") or "")
    body = _norm_text(title, company, location, description)
    title_and_desc = _norm_text(title, description)

    # ---- 1) Region gate -------------------------------------------
    allowed = _allowed_countries(rules)
    if allowed:
        country = detect_country(location)
        if country and country.lower() != "europe":
            if country.lower() not in allowed:
                return {
                    "ok": False,
                    "reason": f"location is {country}, not in your allowed countries",
                }
        elif country is None:
            style = _detect_work_style(job)
            if style == "remote" or not location.strip():
                if not rules.get("allow_remote_unknown", True):
                    return {
                        "ok": False,
                        "reason": "remote posting without a country and "
                        "allow_remote_unknown is false",
                    }
            else:
                return {
                    "ok": False,
                    "reason": f"location '{location}' does not match an allowed "
                    "European country",
                }

    # ---- 2) Company blocklist --------------------------------------
    for blocked in rules.get("excluded_companies", []) or []:
        if str(blocked).strip().lower() in company.lower():
            return {"ok": False, "reason": f"company '{company}' is excluded"}

    # ---- 3) Keyword gates ------------------------------------------
    missing = [
        k
        for k in (rules.get("required_keywords", []) or [])
        if str(k).strip().lower() not in body
    ]
    if missing:
        return {"ok": False, "reason": f"posting is missing required term(s): {', '.join(missing)}"}

    for forbidden in rules.get("excluded_keywords", []) or []:
        if str(forbidden).strip().lower() in body:
            return {"ok": False, "reason": f"posting contains excluded term '{forbidden}'"}

    # ---- 4) Work-style gate -----------------------------------------
    policy = str(rules.get("work_style", "any")).strip().lower()
    if policy != "any":
        style = _detect_work_style(job)
        if style is None:
            if "remote" in body or "work from home" in body or "wfh" in body:
                style = "remote"
        if style != policy:
            return {
                "ok": False,
                "reason": f"work style is '{style or 'unknown'}', rule requires '{policy}'",
            }

    # ---- 5) Employment type / level (any-of match) ------------------
    employment = [str(e).strip().lower() for e in (rules.get("employment_keywords", []) or []) if str(e).strip()]
    if employment and not any(e in title_and_desc for e in employment):
        return {"ok": False, "reason": "posting does not mention expected employment type"}

    levels = [str(e).strip().lower() for e in (rules.get("level_keywords", []) or []) if str(e).strip()]
    if levels and not any(e in title_and_desc for e in levels):
        return {"ok": False, "reason": "posting does not mention expected seniority level"}

    min_n = rules.get("min_applicants", 0) or 0
    max_n = rules.get("max_applicants", 0) or 0
    count = job_applicant_count(job)
    if not applicant_count_allowed(count if count is not None else "Unknown", min_n, max_n):
        return {
            "ok": False,
            "reason": f"applicants {count} outside min={min_n} max={max_n}",
        }

    posted_window = rules.get("posted_within", "all")
    posted_text = job.get("posted") or job.get("Posted") or ""
    if not posted_within(posted_text, posted_window):
        return {
            "ok": False,
            "reason": f"posted '{posted_text}' is older than {posted_window}",
        }

    return {"ok": True, "reason": ""}
