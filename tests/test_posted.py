"""Posted-time windows for search and local filtering."""

from jobagent.posted import (
    parse_posted_age,
    posted_within,
    to_linkedin_tpr,
    window_seconds,
)
from jobagent.rules import evaluate


def test_to_linkedin_tpr_uses_official_buckets():
    assert to_linkedin_tpr("2h") == "r86400"
    assert to_linkedin_tpr("5h") == "r86400"
    assert to_linkedin_tpr("7h") == "r86400"
    assert to_linkedin_tpr("24h") == "r86400"
    assert to_linkedin_tpr("2day") == "r604800"
    assert to_linkedin_tpr("7day") == "r604800"
    assert to_linkedin_tpr("all") == ""
    assert to_linkedin_tpr("r86400") == "r86400"


def test_window_seconds():
    assert window_seconds("2h") == 2 * 3600
    assert window_seconds("5h") == 5 * 3600
    assert window_seconds("7h") == 7 * 3600
    assert window_seconds("2day") == 2 * 86400
    assert window_seconds("all") is None


def test_parse_posted_age():
    assert parse_posted_age("just now") == 0
    assert parse_posted_age("2 hours ago") == 2 * 3600
    assert parse_posted_age("5h") == 5 * 3600
    assert parse_posted_age("2 days ago") == 2 * 86400
    assert parse_posted_age("yesterday") == 24 * 3600
    assert parse_posted_age("") is None


def test_posted_within():
    assert posted_within("2 hours ago", "5h") is True
    assert posted_within("2 days ago", "5h") is False
    assert posted_within("2 days ago", "7day") is True
    assert posted_within("2 days ago", "all") is True
    assert posted_within("", "2h") is True


def test_rules_skip_old_posting():
    job = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany",
        "description": "Python role",
        "posted": "2 days ago",
        "applicants": 12,
    }
    rules = {
        "allow_countries": [],
        "work_style": "any",
        "posted_within": "7h",
    }
    decision = evaluate(job, rules)
    assert decision["ok"] is False
    assert "posted" in decision["reason"]


def test_rules_keep_recent_posting():
    job = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany",
        "description": "Python role",
        "posted": "3 hours ago",
        "applicants": 12,
    }
    rules = {"allow_countries": [], "work_style": "any", "posted_within": "7h"}
    assert evaluate(job, rules)["ok"] is True
