"""Posted-time windows for LinkedIn search and local filtering.

Accepted labels: 2h, 5h, 7h, 24h, 2day, 7day, all
"""

from __future__ import annotations

import re

WINDOW_SECONDS = {
    "2h": 2 * 3600,
    "5h": 5 * 3600,
    "7h": 7 * 3600,
    "24h": 24 * 3600,
    "2d": 2 * 86400,
    "2day": 2 * 86400,
    "2days": 2 * 86400,
    "7d": 7 * 86400,
    "7day": 7 * 86400,
    "7days": 7 * 86400,
    "week": 7 * 86400,
}

# LinkedIn search only exposes 24h / week / month / any.
LINKEDIN_TPR_BUCKETS = (86400, 604800, 2592000)

ALL_LABELS = {"", "all", "any", "anytime", "all time", "alltime"}


def normalize_window(value) -> str:
    if value is None:
        return "all"
    text = str(value).strip().lower().replace("_", " ").replace("-", "")
    text = re.sub(r"\s+", " ", text)
    if text in ALL_LABELS or text in ("r0", "0"):
        return "all"
    compact = text.replace(" ", "")
    aliases = {
        "2hour": "2h",
        "2hours": "2h",
        "5hour": "5h",
        "5hours": "5h",
        "7hour": "7h",
        "7hours": "7h",
        "24hour": "24h",
        "24hours": "24h",
        "1day": "24h",
        "1d": "24h",
        "past24hours": "24h",
        "pastweek": "7day",
        "lastweek": "7day",
        "last24h": "24h",
        "last24hours": "24h",
    }
    if compact in aliases:
        return aliases[compact]
    if compact in WINDOW_SECONDS:
        return compact
    if text in WINDOW_SECONDS:
        return text
    if re.fullmatch(r"r\d+", compact):
        return compact
    return compact or "all"


def window_seconds(value) -> int | None:
    """Seconds for a window label. None means all time (no cap)."""
    label = normalize_window(value)
    if label == "all":
        return None
    if label in WINDOW_SECONDS:
        return WINDOW_SECONDS[label]
    match = re.fullmatch(r"r(\d+)", label)
    if match:
        return int(match.group(1))
    return None


def to_linkedin_tpr(value) -> str:
    """LinkedIn f_TPR: smallest official bucket that covers the window.

    Empty string means any time. Custom hour windows (2h/5h/7h) use past 24h
    on LinkedIn, then local posted-text filtering tightens the result.
    """
    if value is None:
        return ""
    raw = str(value).strip()
    if re.fullmatch(r"r0", raw.lower()):
        return ""
    seconds = window_seconds(raw)
    if seconds is None:
        return ""
    for bucket in LINKEDIN_TPR_BUCKETS:
        if seconds <= bucket:
            return f"r{bucket}"
    return ""


def parse_posted_age(text) -> int | None:
    """Approximate age in seconds from LinkedIn posted text. None if unknown."""
    if text is None:
        return None
    try:
        lowered = str(text).replace("\xa0", " ").strip().lower()
    except Exception:
        return None
    if not lowered:
        return None
    if re.search(r"just now|moments? ago|seconds? ago", lowered):
        return 0
    if re.search(r"\btoday\b", lowered):
        return 12 * 3600
    if re.search(r"\byesterday\b", lowered):
        return 24 * 3600
    compact = re.search(r"(\d+)\s*(h|d|w|m)\b", lowered)
    if compact:
        n = int(compact.group(1))
        unit = compact.group(2)
        spans = {"h": 3600, "d": 86400, "w": 7 * 86400, "m": 30 * 86400}
        return n * spans[unit]
    match = re.search(
        r"(?:an?|1)?\s*(\d+)?\s*(minute|hour|day|week|month)s?\s+ago",
        lowered,
    )
    if not match:
        if re.search(r"\ba minute ago\b", lowered):
            return 60
        if re.search(r"\ban hour ago\b", lowered):
            return 3600
        if re.search(r"\ba day ago\b", lowered):
            return 86400
        if re.search(r"\ba week ago\b", lowered):
            return 7 * 86400
        if re.search(r"\ba month ago\b", lowered):
            return 30 * 86400
        return None
    amount = match.group(1)
    unit = match.group(2)
    n = int(amount) if amount else 1
    spans = {
        "minute": 60,
        "hour": 3600,
        "day": 86400,
        "week": 7 * 86400,
        "month": 30 * 86400,
    }
    return n * spans[unit]


def posted_within(text, window) -> bool:
    """True if posted text is inside the window. Unknown ages pass."""
    seconds = window_seconds(window)
    if seconds is None:
        return True
    age = parse_posted_age(text)
    if age is None:
        return True
    return age <= seconds
