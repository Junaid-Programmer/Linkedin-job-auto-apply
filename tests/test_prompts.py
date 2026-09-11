"""Startup prompts for search options."""

import pytest

from jobagent.prompts import (
    apply_run_options,
    parse_applicants,
    parse_posted,
    prompt_run_options,
    resolve_run_options,
    run_options_from_answers,
)


def test_blank_applicants_means_all():
    assert parse_applicants("") == (0, 0)
    assert parse_applicants("  ") == (0, 0)


def test_applicants_max_only():
    assert parse_applicants("50") == (0, 50)


def test_applicants_range():
    assert parse_applicants("10-50") == (10, 50)
    assert parse_applicants("10 to 50") == (10, 50)


def test_blank_posted_means_all():
    assert parse_posted("") == "all"
    assert parse_posted("  ") == "all"


def test_posted_window():
    assert parse_posted("24h") == "24h"
    assert parse_posted("2h") == "2h"
    assert parse_posted("7day") == "7day"


def test_run_options_require_keywords_and_location():
    opts = run_options_from_answers(
        {
            "keywords": "python developer",
            "location": "Europe",
            "applicants": "",
            "posted": "",
        }
    )
    assert opts["keywords"] == "python developer"
    assert opts["location"] == "Europe"
    assert opts["work_style"] == "remote"
    assert opts["min_applicants"] == 0
    assert opts["max_applicants"] == 0
    assert opts["posted_within"] == "all"


def test_run_options_reject_blank_keywords():
    with pytest.raises(ValueError, match="keywords"):
        run_options_from_answers(
            {"keywords": "", "location": "Europe", "applicants": "", "posted": ""}
        )


def test_run_options_reject_blank_location():
    with pytest.raises(ValueError, match="location"):
        run_options_from_answers(
            {"keywords": "python", "location": "", "applicants": "", "posted": ""}
        )


def test_run_options_apply_filters():
    opts = run_options_from_answers(
        {
            "keywords": "python",
            "location": "Germany",
            "applicants": "50",
            "posted": "24h",
        }
    )
    assert opts["work_style"] == "remote"
    assert opts["max_applicants"] == 50
    assert opts["posted_within"] == "24h"


def test_prompt_asks_keywords_location_applicants_posted_not_work_style():
    answers = iter(["python developer", "Europe", "", "24h"])
    asked = []

    def fake_input(prompt=""):
        asked.append(prompt)
        return next(answers)

    opts = prompt_run_options(input_fn=fake_input)
    joined = " ".join(asked).lower()
    assert "keyword" in joined
    assert "location" in joined or "country" in joined
    assert "applicant" in joined
    assert "posted" in joined
    assert "work style" not in joined
    assert opts["work_style"] == "remote"
    assert opts["keywords"] == "python developer"
    assert opts["location"] == "Europe"
    assert opts["posted_within"] == "24h"


def test_apply_run_options_overlays_this_run_only():
    rules = {
        "linkedin_location": "Europe",
        "work_style": "any",
        "min_applicants": 5,
        "max_applicants": 10,
        "posted_within": "24h",
        "excluded_keywords": ["unpaid"],
    }
    original = dict(rules)
    merged = apply_run_options(
        rules,
        {
            "keywords": "python",
            "location": "Germany",
            "work_style": "remote",
            "min_applicants": 0,
            "max_applicants": 50,
            "posted_within": "all",
        },
    )
    assert merged["linkedin_location"] == "Germany"
    assert merged["work_style"] == "remote"
    assert merged["min_applicants"] == 0
    assert merged["max_applicants"] == 50
    assert merged["posted_within"] == "all"
    assert merged["excluded_keywords"] == ["unpaid"]
    assert rules == original


def test_resolve_run_options_uses_flags_without_prompt():
    class Args:
        keywords = "python"
        location = "Europe"
        time_filter = "24h"
        applicants = "50"

    called = []
    opts = resolve_run_options(Args(), input_fn=lambda p: called.append(p) or "")
    assert called == []
    assert opts["keywords"] == "python"
    assert opts["location"] == "Europe"
    assert opts["work_style"] == "remote"
    assert opts["max_applicants"] == 50
    assert opts["posted_within"] == "24h"


def test_resolve_run_options_keeps_partial_flags():
    class Args:
        keywords = "python"
        location = None
        time_filter = "24h"
        applicants = "50"

    answers = iter(["Germany"])
    asked = []

    def fake_input(prompt=""):
        asked.append(prompt)
        return next(answers)

    opts = resolve_run_options(Args(), input_fn=fake_input)
    assert opts["keywords"] == "python"
    assert opts["location"] == "Germany"
    assert opts["posted_within"] == "24h"
    assert opts["max_applicants"] == 50
    assert opts["work_style"] == "remote"
    joined = " ".join(asked).lower()
    assert "location" in joined or "country" in joined
    assert "keyword" not in joined
    assert "applicant" not in joined
    assert "posted" not in joined


def test_resolve_run_options_prompts_when_flags_missing():
    class Args:
        keywords = None
        location = None
        time_filter = None
        applicants = None

    answers = iter(["java", "Germany", "", ""])
    opts = resolve_run_options(Args(), input_fn=lambda p: next(answers))
    assert opts["keywords"] == "java"
    assert opts["location"] == "Germany"
    assert opts["posted_within"] == "all"
    assert opts["work_style"] == "remote"
