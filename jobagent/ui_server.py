from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jobagent.config import Config
from jobagent.google_oauth import (
    CLIENT_FILE,
    SCOPES,
    TOKEN_FILE,
    client_configured,
    credentials_from_token,
    google_connected,
    list_spreadsheets,
    list_tabs,
)
from jobagent.linkedin import LinkedInScraper, LinkedInSession, login_interactive
from jobagent.posted import to_linkedin_tpr
from jobagent.sheets import JobSheet
from jobagent.ui_run import execute_ui_run
from jobagent.ui_state import load_ui_state, save_ui_state

INDEX_PATH = Path(__file__).resolve().parent / "web" / "index.html"
HOST = "127.0.0.1"
PORT = 8765


def _linkedin_connected(state_file: str) -> bool:
    path = Path(state_file)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    cookies = data.get("cookies") or []
    return any(c.get("name") == "li_at" and c.get("value") for c in cookies)


class UiApp:
    def __init__(
        self,
        state_file: str | None = None,
        connect_fn=None,
        login_fn=None,
        scrape_fn=None,
        upsert_fn=None,
    ) -> None:
        config = Config.from_env()
        self.state_file = state_file or config.state_file
        self.search_pages = config.search_pages
        self.login_fn = login_fn or login_interactive
        self.connect_fn = connect_fn or self._google_connect
        self.scrape_fn = scrape_fn
        self.upsert_fn = upsert_fn
        self._lock = threading.Lock()
        self._run_status = "idle"
        self._scraped = None
        self._reason = ""
        self._spreadsheets: list = []
        self._tabs: list = []

    def snapshot(self) -> dict:
        state = load_ui_state()
        with self._lock:
            run_status = self._run_status
            scraped = self._scraped
            reason = self._reason
            spreadsheets = list(self._spreadsheets)
            tabs = list(self._tabs)
        google = google_connected()
        spreadsheet_id = state.get("spreadsheet_id", "")
        if google and not spreadsheets:
            spreadsheets = self._load_spreadsheets()
            with self._lock:
                self._spreadsheets = spreadsheets
        if google and spreadsheet_id and not tabs:
            tabs = self._load_tabs(spreadsheet_id)
            with self._lock:
                self._tabs = tabs
        return {
            "linkedin": _linkedin_connected(self.state_file),
            "google": google,
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_name": state.get("spreadsheet_name", ""),
            "tab_name": state.get("tab_name", ""),
            "run_status": run_status,
            "scraped": scraped,
            "reason": reason,
            "spreadsheets": spreadsheets,
            "tabs": tabs,
        }

    def select(self, payload: dict) -> dict:
        save_ui_state(
            {
                "spreadsheet_id": payload.get("spreadsheet_id", ""),
                "spreadsheet_name": payload.get("spreadsheet_name", ""),
                "tab_name": payload.get("tab_name", ""),
            }
        )
        sid = payload.get("spreadsheet_id") or ""
        if sid:
            tabs = self._load_tabs(sid)
            with self._lock:
                self._tabs = tabs
        return self.snapshot()

    def start_run(self, payload: dict) -> dict:
        with self._lock:
            if self._run_status == "running":
                already = True
            else:
                already = False
                self._run_status = "running"
                self._scraped = None
                self._reason = ""
        if already:
            return self.snapshot()
        status = self.snapshot()
        status["keywords"] = payload.get("keywords", "")
        status["country"] = payload.get("country", "")
        thread = threading.Thread(
            target=self._run_worker, args=(status, payload), daemon=True
        )
        thread.start()
        return self.snapshot()

    def connect_linkedin(self) -> dict:
        try:
            self.login_fn(self.state_file)
            with self._lock:
                self._reason = ""
        except Exception as exc:
            with self._lock:
                self._reason = str(exc)
        return self.snapshot()

    def connect_google(self) -> dict:
        try:
            self.connect_fn()
            with self._lock:
                self._reason = ""
            self._spreadsheets = self._load_spreadsheets()
        except Exception as exc:
            with self._lock:
                self._reason = str(exc)
        return self.snapshot()

    def spreadsheets(self) -> list:
        rows = self._load_spreadsheets()
        with self._lock:
            self._spreadsheets = rows
        return rows

    def tabs(self, spreadsheet_id: str) -> list:
        rows = self._load_tabs(spreadsheet_id)
        with self._lock:
            self._tabs = rows
        return rows

    def _run_worker(self, status: dict, payload: dict) -> None:
        result = execute_ui_run(status, payload, self._scrape, self._upsert)
        with self._lock:
            self._run_status = result.get("status") or "failed"
            self._scraped = result.get("scraped", 0)
            self._reason = result.get("reason") or ""

    def _scrape(self, filters: dict) -> list:
        if self.scrape_fn is not None:
            return self.scrape_fn(filters)
        session = LinkedInSession(self.state_file, headless=True)
        session.start()
        try:
            if not session.logged_in:
                raise RuntimeError("Connect LinkedIn")
            scraper = LinkedInScraper(session)
            return scraper.scrape_search(
                keywords=filters["keywords"],
                location=filters["country"],
                max_pages=filters.get("pages") or self.search_pages,
                time_filter=to_linkedin_tpr(filters.get("posted") or "all"),
                f_WT=filters.get("f_WT") or "",
                f_JT=filters.get("f_JT") or "",
            )
        finally:
            session.close()

    def _upsert(self, jobs: list) -> tuple:
        if self.upsert_fn is not None:
            return self.upsert_fn(jobs)
        state = load_ui_state()
        sheet = JobSheet(
            credentials=credentials_from_token(),
            sheet_id=state.get("spreadsheet_id") or "",
            worksheet_title=state.get("tab_name") or "",
        )
        return sheet.upsert_jobs(jobs)

    def _google_connect(self) -> None:
        if not client_configured(CLIENT_FILE):
            raise RuntimeError(
                "google_oauth_client.json is missing. Copy "
                "google_oauth_client.json.example to google_oauth_client.json "
                "and fill in the Desktop client."
            )
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path = Path(TOKEN_FILE)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    def _load_spreadsheets(self) -> list:
        if not google_connected():
            return []
        try:
            import gspread

            client = gspread.authorize(credentials_from_token())
            return list_spreadsheets(client)
        except Exception as exc:
            with self._lock:
                self._reason = str(exc) or "Failed to list spreadsheets"
            return []

    def _load_tabs(self, spreadsheet_id: str) -> list:
        if not spreadsheet_id or not google_connected():
            return []
        try:
            import gspread

            client = gspread.authorize(credentials_from_token())
            return list_tabs(client.open_by_key(spreadsheet_id))
        except Exception as exc:
            with self._lock:
                self._reason = str(exc) or "Failed to list tabs"
            return []


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                self._send_html(INDEX_PATH.read_bytes())
                return
            if parsed.path == "/api/status":
                self._send_json(app.snapshot())
                return
            if parsed.path == "/api/spreadsheets":
                fn = getattr(app, "spreadsheets", None)
                self._send_json(fn() if callable(fn) else [])
                return
            if parsed.path == "/api/tabs":
                sid = (parse_qs(parsed.query).get("spreadsheet_id") or [""])[0]
                fn = getattr(app, "tabs", None)
                self._send_json(fn(sid) if callable(fn) else [])
                return
            self._send_json({"reason": "not found"}, code=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/select":
                self._send_json(app.select(self._read_json()))
                return
            if parsed.path == "/api/run":
                self._send_json(app.start_run(self._read_json()))
                return
            if parsed.path == "/api/linkedin/connect":
                fn = getattr(app, "connect_linkedin", None)
                self._send_json(fn() if callable(fn) else app.snapshot())
                return
            if parsed.path == "/api/google/connect":
                fn = getattr(app, "connect_google", None)
                self._send_json(fn() if callable(fn) else app.snapshot())
                return
            self._send_json({"reason": "not found"}, code=404)

        def log_message(self, format, *args):
            return

        def _read_json(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, data, code=200):
            raw = json.dumps(data).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, raw: bytes):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return Handler


def serve_app(app=None, host=HOST, port=PORT, open_browser=False):
    app = app or UiApp()
    httpd = HTTPServer((host, port), make_handler(app))
    if open_browser:
        bound = httpd.server_address[1]
        webbrowser.open(f"http://{host}:{bound}/")
    httpd.serve_forever()
    return httpd


def main() -> None:
    serve_app(host=HOST, port=PORT, open_browser=True)
