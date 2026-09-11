from jobagent.scoring import keyword_score

PYTHON_PROFILE = """
## Skills
- Python
- FastAPI
- PostgreSQL

## Preferences
- Roles: Python Developer, Backend Engineer
"""

OPS_PROFILE = """
## Skills
- Calendar management
- Inbox management
- Customer support

## Preferences
- Roles: Virtual Assistant, Operations Coordinator
"""

PYTHON_JOB = {
    "title": "Senior Python Developer",
    "company": "Acme",
    "location": "Remote",
    "description": "Build FastAPI services with PostgreSQL and Python.",
}


def test_python_profile_scores_python_job_as_target():
    result = keyword_score(PYTHON_JOB, PYTHON_PROFILE)
    assert result["score"] >= 70


def test_ops_profile_does_not_overscore_python_job():
    result = keyword_score(PYTHON_JOB, OPS_PROFILE)
    assert result["score"] < 70


def test_preferred_keywords_raise_score():
    job = {
        "title": "Engineer",
        "company": "Acme",
        "location": "Remote",
        "description": "Rust and WebAssembly services.",
    }
    profile = """
## Skills
- Go

## Preferences
- Roles: Software Engineer
"""
    without = keyword_score(job, profile, preferred_keywords=[])
    with_pref = keyword_score(job, profile, preferred_keywords=["Rust", "WebAssembly"])
    assert with_pref["score"] > without["score"]
