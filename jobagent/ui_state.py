from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = "data/ui_state.json"

_KNOWN_KEYS = ("spreadsheet_id", "spreadsheet_name", "tab_name")


def load_ui_state(path: str = DEFAULT_PATH) -> dict:
    state = {
        "spreadsheet_id": "",
        "spreadsheet_name": "",
        "tab_name": "",
    }
    file_path = Path(path)
    if not file_path.exists():
        return state
    data = json.loads(file_path.read_text(encoding="utf-8"))
    for key in _KNOWN_KEYS:
        if key in data:
            state[key] = data[key]
    return state


def save_ui_state(state: dict, path: str = DEFAULT_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: state.get(key, "") for key in _KNOWN_KEYS}
    for key, value in state.items():
        if key not in payload:
            payload[key] = value
    file_path.write_text(json.dumps(payload), encoding="utf-8")
