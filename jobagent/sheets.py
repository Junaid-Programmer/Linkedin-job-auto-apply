"""Google Sheets integration via a service account (gspread).

The spreadsheet is created automatically if it does not exist. Jobs are
upserted by their LinkedIn job ID so re-runs never duplicate rows.
"""

from __future__ import annotations

from typing import Optional

import gspread
from google.oauth2 import service_account

HEADERS = [
    "Timestamp",
    "Job ID",
    "Title",
    "Company",
    "Location",
    "Posted",
    "LinkedIn URL",
    "Description",
    "Applications Submitted",
    "Score",
    "Match Reasons",
    "Status",
    "Apply Package",
]

# Column letters (1-indexed) for the fields we update after scoring.
APPLICANTS_COL = 9
SCORE_COL = 10
REASONS_COL = 11
STATUS_COL = 12
PACKAGE_COL = 13


class JobSheet:
    def __init__(self, service_account_file: str, sheet_name: str, sheet_id: str = "") -> None:
        self.sheet_name = sheet_name
        self.sheet_id = sheet_id
        self.client = self._build_client(service_account_file)
        self.sheet = self._ensure_sheet()

    @staticmethod
    def _build_client(service_account_file: str) -> gspread.Client:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
        )
        return gspread.authorize(credentials)

    def _ensure_sheet(self):
        if self.sheet_id:
            try:
                spreadsheet = self.client.open_by_key(self.sheet_id)
            except gspread.SpreadsheetNotFound:
                raise RuntimeError(
                    f"Could not open spreadsheet by ID {self.sheet_id}. "
                    "Share it with the service account email (Editor access)."
                )
        else:
            try:
                spreadsheet = self.client.open(self.sheet_name)
            except gspread.SpreadsheetNotFound:
                spreadsheet = self.client.create(self.sheet_name)
        worksheet = spreadsheet.sheet1
        first_row = worksheet.row_values(1)
        old_headers = [
            "Timestamp",
            "Job ID",
            "Title",
            "Company",
            "Location",
            "Posted",
            "LinkedIn URL",
            "Description",
            "Score",
            "Match Reasons",
            "Status",
            "Apply Package",
        ]
        if first_row[: len(old_headers)] == old_headers and "Applications Submitted" not in first_row:
            worksheet.insert_cols([["Applications Submitted"]], col=9)
            first_row = worksheet.row_values(1)
        if first_row[: len(HEADERS)] != HEADERS:
            if not any(first_row):
                worksheet.update("A1", [HEADERS])
            elif first_row != HEADERS:
                worksheet.insert_row(HEADERS, 1)
        return spreadsheet

    def worksheet(self):
        return self.sheet.sheet1

    def _job_ids(self) -> set[str]:
        worksheet = self.worksheet()
        values = worksheet.col_values(2)  # "Job ID" column
        return {str(v).strip() for v in values if str(v).strip() and str(v).strip() != "Job ID"}

    def upsert_jobs(self, jobs: list[dict]) -> tuple[int, int]:
        """Append jobs that are not already tracked.

        Returns (added, skipped) counts.
        """
        from datetime import datetime, timezone

        worksheet = self.worksheet()
        existing = self._job_ids()
        rows = []
        for job in jobs:
            job_id = str(job.get("id") or job.get("url") or "")
            if not job_id or job_id in existing:
                continue
            existing.add(job_id)
            applicants = job.get("applicants")
            if applicants is None:
                applicants = job.get("applicant_count") or job.get("applications_submitted") or ""
            rows.append(
                [
                    datetime.now(timezone.utc).isoformat(),
                    job_id,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("posted", ""),
                    job.get("url", ""),
                    job.get("description", ""),
                    applicants if applicants not in (None, "") else "",
                    "",
                    "",
                    "NEW",
                    "",
                ]
            )
        if rows:
            worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        return len(rows), len(jobs) - len(rows)

    def get_unscored(self) -> list[dict]:
        """Return rows that still have an empty Score column."""
        worksheet = self.worksheet()
        records = worksheet.get_all_records()
        return [r for r in records if _as_float(r.get("Score")) is None]

    def update_score(self, job_id: str, score: int, reasons: str) -> None:
        worksheet = self.worksheet()
        row = self._find_row(job_id)
        if row:
            worksheet.update_cell(row, SCORE_COL, score)
            worksheet.update_cell(row, REASONS_COL, reasons[:500])

    def update_status(self, job_id: str, status: str, package_path: str = "") -> None:
        worksheet = self.worksheet()
        row = self._find_row(job_id)
        if row:
            worksheet.update_cell(row, STATUS_COL, status)
            if package_path:
                worksheet.update_cell(row, PACKAGE_COL, package_path)

    def finalize_rows(self, updates: list[dict]) -> int:
        """Apply score / reasons / status / package updates in ONE read and
        ONE write (avoids the Sheets per-minute read quota).

        Each update dict may contain: job_id (required), score, reasons,
        status, package.
        """
        if not updates:
            return 0
        worksheet = self.worksheet()
        ids = worksheet.col_values(2)
        row_of: dict[str, int] = {}
        for idx, value in enumerate(ids, start=1):
            value = str(value).strip()
            if value and value != "Job ID":
                row_of[value] = idx

        SCORE_COL = 10
        REASONS_COL = 11
        STATUS_COL = 12
        PACKAGE_COL = 13
        APPLICANTS_COL = 9
        _LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        cells = []
        for u in updates:
            row = row_of.get(str(u["job_id"]))
            if row is None:
                continue
            if "applicants" in u and u.get("applicants") is not None:
                cells.append(
                    {"range": f"{_LETTERS[APPLICANTS_COL-1]}{row}", "values": [[u["applicants"]]]}
                )
            if "score" in u and u.get("score") is not None:
                cells.append({"range": f"{_LETTERS[SCORE_COL-1]}{row}", "values": [[u["score"]]]})
            if "reasons" in u:
                cells.append(
                    {"range": f"{_LETTERS[REASONS_COL-1]}{row}", "values": [[str(u["reasons"])[:500]]]}
                )
            if "status" in u:
                cells.append({"range": f"{_LETTERS[STATUS_COL-1]}{row}", "values": [[u["status"]]]})
            if u.get("package"):
                cells.append({"range": f"{_LETTERS[PACKAGE_COL-1]}{row}", "values": [[u["package"]]]})
        if cells:
            worksheet.batch_update(cells, value_input_option="USER_ENTERED")
        return len(cells)

    def _find_row(self, job_id: str) -> Optional[int]:
        worksheet = self.worksheet()
        values = worksheet.col_values(2)
        for idx, value in enumerate(values, start=1):
            if str(value).strip() == str(job_id):
                return idx
        return None


def _as_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
