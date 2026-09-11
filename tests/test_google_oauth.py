from pathlib import Path

from jobagent.google_oauth import (
    client_configured,
    google_connected,
    list_spreadsheets,
    list_tabs,
    token_exists,
)


class FakeSheet:
    def __init__(self, sid, title):
        self.id = sid
        self.title = title


class FakeClient:
    def openall(self):
        return [FakeSheet("id1", "Linkedin Jobs"), FakeSheet("id2", "Other")]


class FakeWs:
    def __init__(self, title):
        self.title = title


class FakeSpreadsheet:
    def worksheets(self):
        return [FakeWs("Jobs"), FakeWs("Control")]


def test_client_and_token_flags(tmp_path: Path):
    missing = tmp_path / "nope.json"
    assert client_configured(str(missing)) is False
    present = tmp_path / "google_oauth_client.json"
    present.write_text("{}", encoding="utf-8")
    assert client_configured(str(present)) is True
    assert token_exists(str(tmp_path / "token.json")) is False


def test_google_connected_false_without_token(tmp_path: Path):
    assert google_connected(str(tmp_path / "token.json")) is False


def test_google_connected_false_for_corrupt_token(tmp_path: Path):
    missing = tmp_path / "missing.json"
    assert google_connected(str(missing)) is False
    corrupt = tmp_path / "token.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    assert google_connected(str(corrupt)) is False


def test_list_spreadsheets_and_tabs():
    rows = list_spreadsheets(FakeClient())
    assert rows == [{"id": "id1", "name": "Linkedin Jobs"}, {"id": "id2", "name": "Other"}]
    assert list_tabs(FakeSpreadsheet()) == ["Jobs", "Control"]
