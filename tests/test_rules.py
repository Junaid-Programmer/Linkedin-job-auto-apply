from jobagent.rules import evaluate, normalize_work_style


def test_normalize_work_style_aliases():
    assert normalize_work_style("remote only") == "remote"
    assert normalize_work_style("remote") == "remote"
    assert normalize_work_style("hybrid only") == "hybrid"
    assert normalize_work_style("on-site only") == "on-site"
    assert normalize_work_style("on site") == "on-site"
    assert normalize_work_style("any") == "any"


def test_remote_only_keeps_remote_job():
    job = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany (Remote)",
        "description": "Python role",
        "posted": "2 hours ago",
        "applicants": 12,
    }
    rules = {
        "allow_countries": ["Germany"],
        "work_style": "remote only",
        "posted_within": "all",
    }
    assert evaluate(job, rules)["ok"] is True


def test_remote_only_skips_onsite_job():
    job = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Berlin, Germany (On-site)",
        "description": "Python role",
        "posted": "2 hours ago",
        "applicants": 12,
    }
    rules = {
        "allow_countries": ["Germany"],
        "work_style": "remote only",
        "posted_within": "all",
    }
    decision = evaluate(job, rules)
    assert decision["ok"] is False
    assert "work style" in decision["reason"]
