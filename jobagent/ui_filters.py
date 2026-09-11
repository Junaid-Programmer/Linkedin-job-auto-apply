from __future__ import annotations

POSTED_OPTIONS = ["2h", "5h", "7h", "24h", "2day", "7day", "all"]

WORK_STYLES = {"Remote": "2", "Hybrid": "3", "On-site": "1"}

JOB_TYPES = {"Full-time": "F", "Part-time": "P", "Contract": "C", "Internship": "I"}

APPLICANT_OPTIONS = {
    "": 999,
    "Less than 5": 4,
    "Less than 10": 9,
    "Less than 15": 14,
    "Less than 25": 24,
    "Less than 40": 39,
}

COUNTRIES = [
    "Austria",
    "Belgium",
    "Bulgaria",
    "Croatia",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Ireland",
    "Italy",
    "Latvia",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Netherlands",
    "Poland",
    "Portugal",
    "Romania",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
    "Iceland",
    "Norway",
    "Switzerland",
    "United States",
    "Canada",
    "United Kingdom",
    "Australia",
]


def title_tokens(keywords: str) -> list[str]:
    return keywords.lower().split()


def title_matches(title: str, keywords: str) -> bool:
    lowered = title.lower()
    return all(token in lowered for token in title_tokens(keywords))


def max_applicants_from_label(label: str) -> int:
    return APPLICANT_OPTIONS[label]


def applicant_allowed(count: int | None, max_n: int) -> bool:
    if count is None:
        return False
    return 0 <= count <= max_n


def parse_ui_filters(payload: dict) -> dict:
    keywords = str(payload.get("keywords", "")).strip()
    country = str(payload.get("country", "")).strip()
    if not keywords or not country:
        raise ValueError("keywords and country are required")
    work_style = payload.get("work_style") or "Remote"
    job_type = payload.get("job_type") or "Full-time"
    posted = payload.get("posted") or "all"
    applicants = payload.get("applicants", "") or ""
    return {
        "keywords": keywords,
        "country": country,
        "posted": posted,
        "work_style": work_style,
        "job_type": job_type,
        "max_applicants": max_applicants_from_label(applicants),
        "f_WT": WORK_STYLES.get(work_style, ""),
        "f_JT": JOB_TYPES.get(job_type, ""),
    }


def linkedin_filter_params(filters: dict) -> dict:
    return {
        "f_WT": filters.get("f_WT") or "",
        "f_JT": filters.get("f_JT") or "",
    }
