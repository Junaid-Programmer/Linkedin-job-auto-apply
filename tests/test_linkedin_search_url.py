from jobagent.linkedin import _build_search_url


def test_search_url_includes_workplace_and_job_type():
    url = _build_search_url("virtual assistant", "United States", 0, "r86400", f_WT="2", f_JT="F")
    assert "keywords=virtual%20assistant" in url
    assert "location=United%20States" in url
    assert "f_TPR=r86400" in url
    assert "f_WT=2" in url
    assert "f_JT=F" in url


def test_search_url_omits_empty_extra_filters():
    url = _build_search_url("python", "Germany", 0, "")
    assert "f_WT=" not in url
    assert "f_JT=" not in url
