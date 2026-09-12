from jobagent.ui_filters import (
    COUNTRIES,
    applicant_allowed,
    max_applicants_from_label,
    parse_ui_filters,
    title_matches,
)


def test_title_matches_all_tokens():
    assert title_matches("Senior Virtual Assistant", "virtual assistant") is True
    assert title_matches("Assistant Manager", "virtual assistant") is False
    assert title_matches("VIRTUAL assistant role", "Virtual Assistant") is True


def test_blank_applicants_is_999():
    assert max_applicants_from_label("") == 999
    assert max_applicants_from_label("Less than 10") == 9


def test_applicant_zero_kept_hidden_skipped():
    assert applicant_allowed(0, 999) is True
    assert applicant_allowed(None, 999) is False
    assert applicant_allowed(1000, 999) is False
    assert applicant_allowed(9, 9) is True
    assert applicant_allowed(10, 9) is False


def test_parse_ui_filters_requires_keywords_and_country():
    try:
        parse_ui_filters({"keywords": "", "country": "United States"})
        assert False, "expected ValueError"
    except ValueError:
        pass
    opts = parse_ui_filters(
        {
            "keywords": "virtual assistant",
            "country": "United States",
            "posted": "24h",
            "work_style": "Remote",
            "job_type": "Full-time",
            "applicants": "Less than 25",
        }
    )
    assert opts["keywords"] == "virtual assistant"
    assert opts["country"] == "United States"
    assert opts["posted"] == "24h"
    assert opts["f_WT"] == "2"
    assert opts["f_JT"] == "F"
    assert opts["max_applicants"] == 24
    assert opts["pages"] == 2
    assert "United States" in COUNTRIES
    assert "Germany" in COUNTRIES
    assert "Australia" in COUNTRIES


def test_parse_ui_filters_pages_default_and_clamp():
    base = {"keywords": "va", "country": "United States"}
    assert parse_ui_filters(base)["pages"] == 2
    assert parse_ui_filters({**base, "pages": 5})["pages"] == 5
    assert parse_ui_filters({**base, "pages": "3"})["pages"] == 3
    assert parse_ui_filters({**base, "pages": ""})["pages"] == 2
    assert parse_ui_filters({**base, "pages": 0})["pages"] == 1
    assert parse_ui_filters({**base, "pages": 99})["pages"] == 10
