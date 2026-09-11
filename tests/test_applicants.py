"""Applicant-count parse and min/max filter."""

from jobagent.applicants import (
    applicant_count_allowed,
    job_applicant_count,
    parse_applicant_count,
)
from jobagent.rules import evaluate


def test_parse_applicant_count():
    assert parse_applicant_count("23 applicants") == 23
    assert parse_applicant_count("Over 200 applicants") == 200
    assert parse_applicant_count("Be among the first 8 applicants") == 8
    assert parse_applicant_count("Posted 2 days ago") is None


def test_applicant_count_allowed():
    assert applicant_count_allowed(23, 0, 0) is True
    assert applicant_count_allowed(200, 0, 50) is False
    assert applicant_count_allowed("Unknown", 0, 50) is False
    assert applicant_count_allowed("Unknown", 0, 0) is True


def test_job_applicant_count_from_sheet_column():
    assert job_applicant_count({"Applications Submitted": 23}) == 23
    assert job_applicant_count({"insight": "Over 200 applicants"}) == 200


def test_rules_skip_too_many_applicants():
    job = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany",
        "description": "Python role",
        "posted": "2 hours ago",
        "applicants": 200,
    }
    rules = {
        "allow_countries": [],
        "excluded_keywords": [],
        "work_style": "any",
        "min_applicants": 0,
        "max_applicants": 50,
    }
    decision = evaluate(job, rules)
    assert decision["ok"] is False
    assert "applicants" in decision["reason"]


def test_rules_keep_when_count_in_range():
    job = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany",
        "description": "Python role",
        "posted": "2 hours ago",
        "applicants": 23,
    }
    rules = {"allow_countries": [], "work_style": "any", "max_applicants": 50}
    assert evaluate(job, rules)["ok"] is True
