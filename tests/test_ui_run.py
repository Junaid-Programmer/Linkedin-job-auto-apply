from jobagent.ui_run import execute_ui_run, filter_scraped_jobs, run_ready


def test_run_ready_requires_connections_and_keywords():
    ok, reason = run_ready(
        {
            "linkedin": False,
            "google": True,
            "spreadsheet_id": "id",
            "tab_name": "Jobs",
            "keywords": "va",
            "country": "United States",
        }
    )
    assert ok is False
    assert "linkedin" in reason.lower()
    ok, _ = run_ready(
        {
            "linkedin": True,
            "google": True,
            "spreadsheet_id": "id",
            "tab_name": "Jobs",
            "keywords": "virtual assistant",
            "country": "United States",
        }
    )
    assert ok is True


def test_filter_keeps_zero_and_title_match():
    jobs = [
        {"id": "1", "title": "Virtual Assistant", "posted": "2 hours ago", "applicants": 0},
        {"id": "2", "title": "Office Manager", "posted": "2 hours ago", "applicants": 3},
        {"id": "3", "title": "Virtual Assistant", "posted": "2 hours ago", "applicants": None},
        {"id": "4", "title": "Virtual Assistant", "posted": "2 hours ago", "applicants": 1000},
    ]
    kept = filter_scraped_jobs(
        jobs,
        {"keywords": "virtual assistant", "posted": "all", "max_applicants": 999},
    )
    assert [j["id"] for j in kept] == ["1"]


def test_execute_ui_run_blocked_does_not_scrape():
    called = []

    def scrape_fn(filters):
        called.append("scrape")
        return []

    result = execute_ui_run(
        {
            "linkedin": False,
            "google": True,
            "spreadsheet_id": "id",
            "tab_name": "Jobs",
            "keywords": "va",
            "country": "United States",
        },
        {"keywords": "va", "country": "United States"},
        scrape_fn,
        lambda jobs: (0, 0),
    )
    assert result["ok"] is False
    assert result["scraped"] == 0
    assert called == []


def test_execute_ui_run_scrapes_filters_upserts():
    def scrape_fn(filters):
        assert filters["keywords"] == "virtual assistant"
        assert filters["pages"] == 4
        return [
            {"id": "1", "title": "Virtual Assistant", "posted": "1 hour ago", "applicants": 2},
            {"id": "2", "title": "Chef", "posted": "1 hour ago", "applicants": 2},
        ]

    upserted = []

    def upsert_fn(jobs):
        upserted.extend(jobs)
        return (len(jobs), 0)

    result = execute_ui_run(
        {
            "linkedin": True,
            "google": True,
            "spreadsheet_id": "id",
            "tab_name": "Jobs",
            "keywords": "virtual assistant",
            "country": "United States",
        },
        {
            "keywords": "virtual assistant",
            "country": "United States",
            "posted": "all",
            "applicants": "",
            "work_style": "Remote",
            "job_type": "Full-time",
            "pages": 4,
        },
        scrape_fn,
        upsert_fn,
    )
    assert result["ok"] is True
    assert result["status"] == "done"
    assert result["scraped"] == 1
    assert [j["id"] for j in upserted] == ["1"]
