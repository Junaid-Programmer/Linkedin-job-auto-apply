from jobagent.control import control_from_row, is_start_truthy, options_from_control


def test_control_from_row_reads_six_columns():
    row = control_from_row(["python", "Europe", "50", "24h", "TRUE", "idle"])
    assert row["keywords"] == "python"
    assert row["location"] == "Europe"
    assert row["applicants"] == "50"
    assert row["posted"] == "24h"
    assert row["start"] is True
    assert row["status"] == "idle"


def test_start_truthy():
    assert is_start_truthy(True) is True
    assert is_start_truthy("TRUE") is True
    assert is_start_truthy("yes") is True
    assert is_start_truthy("1") is True
    assert is_start_truthy(False) is False
    assert is_start_truthy("") is False
    assert is_start_truthy("FALSE") is False


def test_options_from_control_blank_means_all():
    opts = options_from_control(
        {"keywords": "python", "location": "Europe", "applicants": "", "posted": ""}
    )
    assert opts["work_style"] == "remote"
    assert opts["min_applicants"] == 0
    assert opts["max_applicants"] == 0
    assert opts["posted_within"] == "all"


def test_options_from_control_requires_keywords_and_location():
    import pytest

    with pytest.raises(ValueError):
        options_from_control({"keywords": "", "location": "Europe", "applicants": "", "posted": ""})
