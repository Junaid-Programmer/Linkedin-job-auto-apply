"""Sheet row layout includes Applications Submitted."""

from jobagent.sheets import HEADERS


def test_headers_include_applications_submitted():
    assert "Posted" in HEADERS
    assert HEADERS.index("Posted") == 5
    assert "Applications Submitted" in HEADERS
    assert HEADERS.index("Applications Submitted") == 8
    assert HEADERS.index("Score") == 9