"""Require posted time and applicant count on every scraped job."""

from jobagent.insights import (
    enrich_from_texts,
    has_required_insights,
    jobs_needing_detail,
    keep_jobs_with_insights,
    posted_line_from_text,
)
from jobagent.rules import evaluate


def test_posted_line_from_card_text():
    assert posted_line_from_text("2 days ago") == "2 days ago"
    assert posted_line_from_text("just now") == "just now"
    assert posted_line_from_text("Reposted 3 hours ago") == "Reposted 3 hours ago"


def test_posted_line_from_detail_mixed_text():
    assert posted_line_from_text("Posted 2 hours ago · Over 100 applicants") == "2 hours ago"
    assert posted_line_from_text("Promoted\n3 weeks ago\nEasy Apply") == "3 weeks ago"
    assert posted_line_from_text("Easy Apply") == ""
    assert posted_line_from_text("Viewed") == ""


def test_has_required_insights_needs_both_fields():
    assert has_required_insights({"posted": "2 hours ago", "applicants": 23}) is True
    assert has_required_insights({"posted": "2 hours ago", "applicants": None}) is False
    assert has_required_insights({"posted": "", "applicants": 23}) is False
    assert has_required_insights({"posted": "2 hours ago", "applicants": "Unknown"}) is False


def test_keep_jobs_with_insights_skips_hidden_applicants():
    jobs = [
        {"id": "1", "posted": "2 hours ago", "applicants": 12},
        {"id": "2", "posted": "2 hours ago", "applicants": None},
        {"id": "3", "posted": "", "applicants": 4},
        {"id": "4", "posted": "yesterday", "applicants": "Unknown"},
    ]
    kept = keep_jobs_with_insights(jobs)
    assert [j["id"] for j in kept] == ["1"]


def test_jobs_needing_detail_includes_missing_insights_with_no_cap():
    jobs = {
        "ok": {"id": "ok", "description": "full", "posted": "2 hours ago", "applicants": 8},
        "no_posted": {"id": "no_posted", "description": "full", "posted": "", "applicants": 8},
        "no_apps": {"id": "no_apps", "description": "full", "posted": "today", "applicants": None},
        "no_desc": {"id": "no_desc", "description": "", "posted": "today", "applicants": 3},
    }
    for i in range(20):
        jobs[f"extra{i}"] = {
            "id": f"extra{i}",
            "description": "",
            "posted": "",
            "applicants": None,
        }
    needed = jobs_needing_detail(jobs)
    assert "ok" not in needed
    assert "no_posted" in needed
    assert "no_apps" in needed
    assert "no_desc" in needed
    assert len(needed) == 23


def test_enrich_from_texts_fills_posted_and_applicants():
    job = {"posted": "", "applicants": None}
    enrich_from_texts(job, ["Promoted", "2 hours ago", "23 applicants"])
    assert job["posted"] == "2 hours ago"
    assert job["applicants"] == 23


def test_enrich_from_texts_does_not_overwrite_existing():
    job = {"posted": "1 hour ago", "applicants": 5}
    enrich_from_texts(job, ["2 days ago", "100 applicants"])
    assert job["posted"] == "1 hour ago"
    assert job["applicants"] == 5


def _job(**extra):
    data = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany",
        "description": "Python role",
    }
    data.update(extra)
    return data


def test_rules_skip_missing_applicants():
    decision = evaluate(_job(posted="2 hours ago"), {"allow_countries": [], "work_style": "any"})
    assert decision["ok"] is False
    assert "applicants" in decision["reason"]


def test_rules_skip_hidden_applicants():
    decision = evaluate(
        _job(posted="2 hours ago", applicants="Unknown"),
        {"allow_countries": [], "work_style": "any"},
    )
    assert decision["ok"] is False
    assert "applicants" in decision["reason"]


def test_rules_skip_missing_posted():
    decision = evaluate(_job(applicants=12), {"allow_countries": [], "work_style": "any"})
    assert decision["ok"] is False
    assert "posted" in decision["reason"]
