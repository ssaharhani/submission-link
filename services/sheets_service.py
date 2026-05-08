"""
sheets_service.py
-----------------
Control plane via Google Sheets.

Sheet tab 1 (Sheet1):
  A2: Status       → "Open" or "Closed"
  B2: Question_ID  → e.g. "Q1"
  C2: Opened_At    → Unix timestamp string when session was opened

Sheet tab 2 (Submissions):
  Tracks which student IDs submitted for which question (duplicate prevention).

Rate limit protection:
  - State is cached for 5 seconds to avoid hammering the Sheets API.
  - All writes are batched into one call.
"""

import time
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

STATUS_COL    = 1
QUESTION_COL  = 2
OPENED_AT_COL = 3
DATA_ROW      = 2
AUTO_CLOSE_MINUTES = 15


@st.cache_resource(ttl=0)
def _get_client() -> gspread.Client:
    creds_dict = dict(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(ttl=0)
def _get_spreadsheet():
    client = _get_client()
    sheet_url = st.secrets["settings"]["sheet_url"]
    return client.open_by_url(sheet_url)


def _get_worksheet():
    return _get_spreadsheet().sheet1


# ── Cached state read (5-second TTL to avoid 429 errors) ─────────────────────

@st.cache_data(ttl=5)
def _fetch_state_from_sheet() -> dict:
    """Reads the sheet. Cached for 5 seconds."""
    ws = _get_worksheet()
    row = ws.row_values(DATA_ROW)
    status      = row[STATUS_COL - 1]    if len(row) >= STATUS_COL    else "Closed"
    question_id = row[QUESTION_COL - 1]  if len(row) >= QUESTION_COL  else "Q1"
    opened_at   = row[OPENED_AT_COL - 1] if len(row) >= OPENED_AT_COL else ""
    return {
        "status": status,
        "question_id": question_id,
        "opened_at": float(opened_at) if opened_at else 0.0,
    }


def get_session_state() -> dict:
    """
    Returns current session state with auto-close logic applied.
    Uses 5-second cache to stay within Sheets quota.
    """
    state = _fetch_state_from_sheet()
    status    = state["status"]
    opened_at = state["opened_at"]

    # Auto-close if session exceeded time limit
    if status == "Open" and opened_at > 0:
        elapsed_minutes = (time.time() - opened_at) / 60
        if elapsed_minutes >= AUTO_CLOSE_MINUTES:
            status = "Closed"
            # Write close to sheet and clear cache
            _get_worksheet().update(f"A{DATA_ROW}", [["Closed"]])
            _fetch_state_from_sheet.clear()

    return {
        "status": status,
        "question_id": state["question_id"],
        "opened_at": opened_at,
    }


def set_session_state(status: str, question_id: str) -> None:
    """Write status + question ID in one batch. Clears cache immediately."""
    opened_at = str(time.time()) if status == "Open" else ""
    _get_worksheet().update(f"A{DATA_ROW}:C{DATA_ROW}", [[status, question_id, opened_at]])
    _fetch_state_from_sheet.clear()  # force fresh read on next call


def ensure_header_row() -> None:
    """Creates header + default Closed row if sheet is brand new."""
    ws = _get_worksheet()
    if ws.cell(1, 1).value != "Status":
        ws.update("A1:C1", [["Status", "Question_ID", "Opened_At"]])
        ws.update(f"A{DATA_ROW}:C{DATA_ROW}", [["Closed", "Q1", ""]])
        _fetch_state_from_sheet.clear()


# ── Submission log (duplicate prevention) ────────────────────────────────────

@st.cache_data(ttl=10)
def _fetch_submissions() -> list:
    """Returns all submission records. Cached 10 seconds."""
    try:
        spreadsheet = _get_spreadsheet()
        try:
            log_sheet = spreadsheet.worksheet("Submissions")
        except gspread.WorksheetNotFound:
            return []
        return log_sheet.get_all_records()
    except Exception:
        return []


def get_student_submissions(question_id: str) -> list:
    """Return list of student IDs that already submitted for this question."""
    records = _fetch_submissions()
    return [
        str(r["Student_ID"])
        for r in records
        if str(r["Question_ID"]) == str(question_id)
    ]


def log_student_submission(question_id: str, student_id: str) -> None:
    """Record submission. Clears submission cache."""
    try:
        spreadsheet = _get_spreadsheet()
        try:
            log_sheet = spreadsheet.worksheet("Submissions")
        except gspread.WorksheetNotFound:
            log_sheet = spreadsheet.add_worksheet("Submissions", rows=1000, cols=3)
            log_sheet.update("A1:C1", [["Question_ID", "Student_ID", "Timestamp"]])

        log_sheet.append_row([str(question_id), str(student_id), str(time.time())])
        _fetch_submissions.clear()
    except Exception:
        pass
