from pathlib import Path


def test_env_example_has_no_real_sheet_id():
    text = Path(".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("GOOGLE_SHEET_ID="):
            value = line.split("=", 1)[1].strip()
            assert value in ("", "your-sheet-id-here")


def test_requirements_include_pytest():
    text = Path("requirements.txt").read_text(encoding="utf-8")
    assert "pytest" in text
