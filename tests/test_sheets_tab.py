from jobagent.sheets import JobSheet, resolve_worksheet


class Spread:
    def __init__(self):
        self.sheet1 = "FIRST"

    def worksheet(self, title):
        return f"TAB:{title}"


def test_resolve_worksheet_named_and_default():
    s = Spread()
    assert resolve_worksheet(s, "") == "FIRST"
    assert resolve_worksheet(s, "Jobs") == "TAB:Jobs"


def test_oauth_open_by_key_does_not_mention_service_account(monkeypatch):
    import gspread

    class FakeClient:
        def open_by_key(self, key):
            raise gspread.SpreadsheetNotFound()

    monkeypatch.setattr(gspread, "authorize", lambda creds: FakeClient())
    try:
        JobSheet(credentials=object(), sheet_id="abc")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "service account" not in msg
        assert "pick another spreadsheet" in msg or "sign in with google" in msg
