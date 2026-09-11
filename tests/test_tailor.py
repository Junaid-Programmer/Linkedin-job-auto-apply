from pathlib import Path

from jobagent.tailor import prepare_application_package_fallback


def test_fallback_note_is_generic(tmp_path: Path):
    job = {
        "id": "123",
        "title": "Python Developer",
        "company": "Acme",
        "location": "Remote",
        "description": "Python FastAPI",
        "url": "https://example.com/jobs/123",
    }
    profile = """
## Skills
- Python
## Preferences
- Roles: Python Developer
"""
    resume = "# Jane Doe\nPython developer"
    folder = prepare_application_package_fallback(job, resume, profile, str(tmp_path))
    note = (Path(folder) / "application_note.md").read_text(encoding="utf-8").lower()
    assert "coaches" not in note
    assert "entrepreneurs" not in note
    assert "python developer" in note
    assert "acme" in note
