from pathlib import Path

from jobagent.ui_state import load_ui_state, save_ui_state


def test_load_missing_returns_empty(tmp_path: Path):
    path = tmp_path / "ui_state.json"
    state = load_ui_state(str(path))
    assert state["spreadsheet_id"] == ""
    assert state["tab_name"] == ""


def test_load_corrupt_json_returns_empty(tmp_path: Path):
    path = tmp_path / "ui_state.json"
    path.write_text("{not-json", encoding="utf-8")
    state = load_ui_state(str(path))
    assert state == {"spreadsheet_id": "", "spreadsheet_name": "", "tab_name": ""}


def test_load_non_dict_json_returns_empty(tmp_path: Path):
    path = tmp_path / "ui_state.json"
    path.write_text("1", encoding="utf-8")
    state = load_ui_state(str(path))
    assert state == {"spreadsheet_id": "", "spreadsheet_name": "", "tab_name": ""}


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "nested" / "ui_state.json"
    save_ui_state(
        {
            "spreadsheet_id": "abc",
            "spreadsheet_name": "Linkedin Jobs",
            "tab_name": "Jobs",
        },
        str(path),
    )
    state = load_ui_state(str(path))
    assert state["spreadsheet_id"] == "abc"
    assert state["spreadsheet_name"] == "Linkedin Jobs"
    assert state["tab_name"] == "Jobs"
