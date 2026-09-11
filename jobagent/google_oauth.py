from __future__ import annotations

from pathlib import Path

from google.oauth2.credentials import Credentials

CLIENT_FILE = "google_oauth_client.json"
TOKEN_FILE = "data/google_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def client_configured(path: str = CLIENT_FILE) -> bool:
    return Path(path).is_file()


def token_exists(path: str = TOKEN_FILE) -> bool:
    return Path(path).is_file()


def credentials_from_token(path: str = TOKEN_FILE):
    token_path = Path(path)
    if not token_path.is_file():
        raise FileNotFoundError(path)
    return Credentials.from_authorized_user_file(str(token_path), SCOPES)


def google_connected(token_path: str = TOKEN_FILE) -> bool:
    if not token_exists(token_path):
        return False
    creds = credentials_from_token(token_path)
    if creds.valid:
        return True
    return bool(creds.expired and creds.refresh_token)


def list_spreadsheets(client) -> list[dict]:
    return [{"id": sheet.id, "name": sheet.title} for sheet in client.listall()]


def list_tabs(spreadsheet) -> list[str]:
    return [ws.title for ws in spreadsheet.worksheets()]
