from pathlib import Path

from jobagent.ui_server import make_handler, serve_app


class FakeApp:
    def __init__(self):
        self.status = {
            "linkedin": False,
            "google": False,
            "spreadsheet_id": "",
            "spreadsheet_name": "",
            "tab_name": "",
            "run_status": "idle",
            "scraped": None,
            "reason": "",
        }
        self.selected = None
        self.run_calls = []

    def snapshot(self):
        return dict(self.status)

    def select(self, payload):
        self.selected = payload
        self.status["spreadsheet_id"] = payload["spreadsheet_id"]
        self.status["tab_name"] = payload["tab_name"]
        return self.snapshot()

    def start_run(self, payload):
        self.run_calls.append(payload)
        self.status["run_status"] = "running"
        return self.snapshot()


def test_status_and_select_and_run_endpoints():
    app = FakeApp()
    Handler = make_handler(app)
    from http.server import HTTPServer
    import json
    import threading
    import urllib.request

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        status = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status").read())
        assert status["run_status"] == "idle"
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/select",
            data=json.dumps({"spreadsheet_id": "abc", "spreadsheet_name": "S", "tab_name": "Jobs"}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        body = json.loads(urllib.request.urlopen(req).read())
        assert body["tab_name"] == "Jobs"
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/run",
            data=json.dumps({"keywords": "va", "country": "United States"}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        body = json.loads(urllib.request.urlopen(req).read())
        assert body["run_status"] == "running"
        assert app.run_calls
    finally:
        httpd.shutdown()


def test_index_html_has_required_labels():
    html = Path("jobagent/web/index.html").read_text(encoding="utf-8")
    for needle in (
        "Connect LinkedIn",
        "Sign in with Google",
        "Title keywords",
        "Posted",
        "Country",
        "Work style",
        "Applicants",
        "Job type",
        "Run",
        "Jobs scraped",
    ):
        assert needle in html
    assert 'run_status === "running"' in html


def test_start_run_while_running_does_not_spawn_thread(monkeypatch):
    from jobagent.ui_server import UiApp

    started = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            started.append("created")

        def start(self):
            started.append("start")

    monkeypatch.setattr("jobagent.ui_server.threading.Thread", FakeThread)
    app = UiApp(state_file="nope")
    app._run_status = "running"
    snap = app.start_run({"keywords": "va", "country": "United States"})
    assert snap["run_status"] == "running"
    assert started == []


def test_load_spreadsheets_sets_reason_on_failure(monkeypatch):
    from jobagent import ui_server

    monkeypatch.setattr(ui_server, "google_connected", lambda *a, **k: True)
    monkeypatch.setattr(ui_server, "credentials_from_token", lambda *a, **k: object())

    import gspread

    def boom(_creds):
        raise RuntimeError("Drive list failed")

    monkeypatch.setattr(gspread, "authorize", boom)
    app = ui_server.UiApp(state_file="nope")
    rows = app._load_spreadsheets()
    assert rows == []
    assert app._reason


def test_load_tabs_sets_reason_on_failure(monkeypatch):
    from jobagent import ui_server

    monkeypatch.setattr(ui_server, "google_connected", lambda *a, **k: True)
    monkeypatch.setattr(ui_server, "credentials_from_token", lambda *a, **k: object())

    import gspread

    def boom(_creds):
        raise RuntimeError("Sheets list failed")

    monkeypatch.setattr(gspread, "authorize", boom)
    app = ui_server.UiApp(state_file="nope")
    rows = app._load_tabs("sid")
    assert rows == []
    assert app._reason
