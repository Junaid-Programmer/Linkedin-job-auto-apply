from jobagent.sheets import HEADERS, header_needs_reset


def test_header_needs_reset_when_mismatch():
    assert header_needs_reset(["Job ID", "Title"]) is True
    assert header_needs_reset(HEADERS) is False
    assert header_needs_reset([]) is True
