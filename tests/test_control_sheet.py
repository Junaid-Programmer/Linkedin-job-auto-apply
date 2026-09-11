import gspread

from jobagent.control import CONTROL_HEADERS
from jobagent.sheets import JobSheet, control_header_needs_reset


def test_control_header_needs_reset():
    assert control_header_needs_reset([]) is True
    assert control_header_needs_reset(CONTROL_HEADERS) is False
    assert control_header_needs_reset(["Keywords"]) is True


class FakeWorksheet:
    def __init__(self, rows=None):
        self._rows = {i: list(r) for i, r in (rows or {}).items()}
        self.updates = []
        self.batch_updates = []

    def row_values(self, n):
        return list(self._rows.get(n, []))

    def update(self, a1, values):
        self.updates.append((a1, values))
        if a1 == "A1":
            self._rows[1] = list(values[0])

    def batch_update(self, cells, value_input_option=None):
        self.batch_updates.append({"cells": cells, "value_input_option": value_input_option})


class FakeSpreadsheet:
    def __init__(self, worksheets=None):
        self._worksheets = dict(worksheets or {})

    def worksheet(self, name):
        if name not in self._worksheets:
            raise gspread.WorksheetNotFound(name)
        return self._worksheets[name]

    def add_worksheet(self, title, rows=100, cols=10):
        ws = FakeWorksheet()
        self._worksheets[title] = ws
        return ws


def _jobsheet(spreadsheet):
    sheet = JobSheet.__new__(JobSheet)
    sheet.sheet = spreadsheet
    return sheet


def test_ensure_control_creates_tab_and_headers():
    spreadsheet = FakeSpreadsheet()
    js = _jobsheet(spreadsheet)
    js._ensure_control(spreadsheet)
    ws = spreadsheet.worksheet("Control")
    assert ws.updates == [("A1", [CONTROL_HEADERS])]


def test_read_control_uses_row_2():
    ws = FakeWorksheet(rows={2: ["python", "Europe", "50", "24h", "TRUE", "idle"]})
    js = _jobsheet(FakeSpreadsheet({"Control": ws}))
    row = js.read_control()
    assert row["keywords"] == "python"
    assert row["start"] is True
    assert row["status"] == "idle"


def test_write_control_updates_e2_and_f2():
    ws = FakeWorksheet()
    js = _jobsheet(FakeSpreadsheet({"Control": ws}))
    js.write_control(start=False, status="running")
    assert ws.batch_updates[0]["cells"] == [
        {"range": "E2", "values": [["FALSE"]]},
        {"range": "F2", "values": [["running"]]},
    ]
