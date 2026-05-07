"""
sheets_service.py
-----------------
All communication with the Google Sheet control plane.

Sheet structure (row 2 is the live data row):
  A: Status       → "Open" or "Closed"
  B: Question_ID  → e.g. "Q1"
  C: Opened_At    → Unix timestamp (float as string) of when session was opened
"""

import time
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

STATUS_COL = 1
QUESTION_COL = 2
OPENED_AT_COL = 3
DATA_ROW = 2

AUTO_CLOSE_MINUTES = 15


@st.cache_resource(ttl=0)
def _get_client() -> gspread.Client:
    creds_dict = dict(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_worksheet() -> gspread.Worksheet:
    client = _get_client()
    sheet_url = st.secrets["settings"]["sheet_url"]
    return client.open_by_url(sheet_url).sheet1


def get_session_state() -> dict:
    """
    Returns current session state. Auto-closes if open for more than
    AUTO_CLOSE_MINUTES minutes.
    """
    ws = _get_worksheet()
    row = ws.row_values(DATA_ROW)

    status = row[STATUS_COL - 1] if len(row) >= STATUS_COL else "Closed"
    question_id = row[QUESTION_COL - 1] if len(row) >= QUESTION_COL else "Q1"
    opened_at = float(row[OPENED_AT_COL - 1]) if len(row) >= OPENED_AT_COL and row[OPENED_AT_COL - 1] else 0.0

    # Auto-close if session has been open too long
    if status == "Open" and opened_at > 0:
        elapsed_minutes = (time.time() - opened_at) / 60
        if elapsed_minutes >= AUTO_CLOSE_MINUTES:
            status = "Closed"
            ws.update(f"A{DATA_ROW}", [["Closed"]])

    return {"status": status, "question_id": question_id, "opened_at": opened_at}


def set_session_state(status: str, question_id: str) -> None:
    """Write status and question ID. Records timestamp when opening."""
    ws = _get_worksheet()
    opened_at = str(time.time()) if status == "Open" else ""
    ws.update(f"A{DATA_ROW}:C{DATA_ROW}", [[status, question_id, opened_at]])


def ensure_header_row() -> None:
    ws = _get_worksheet()
    if ws.cell(1, 1).value != "Status":
        ws.update("A1:C1", [["Status", "Question_ID", "Opened_At"]])
        ws.update(f"A{DATA_ROW}:C{DATA_ROW}", [["Closed", "Q1", ""]])


def get_student_submissions(question_id: str) -> list:
    """Return list of student IDs that already submitted for this question."""
    ws = _get_worksheet()
    try:
        # Submissions tracked in a second sheet tab
        spreadsheet = _get_client().open_by_url(st.secrets["settings"]["sheet_url"])
        try:
            log_sheet = spreadsheet.worksheet("Submissions")
        except gspread.WorksheetNotFound:
            log_sheet = spreadsheet.add_worksheet("Submissions", rows=1000, cols=3)
            log_sheet.update("A1:C1", [["Question_ID", "Student_ID", "Timestamp"]])
            return []

        records = log_sheet.get_all_records()
        return [
            r["Student_ID"]
            for r in records
            if str(r["Question_ID"]) == str(question_id)
        ]
    except Exception:
        return []


def log_student_submission(question_id: str, student_id: str) -> None:
    """Record that a student submitted for this question."""
    try:
        spreadsheet = _get_client().open_by_url(st.secrets["settings"]["sheet_url"])
        try:
            log_sheet = spreadsheet.worksheet("Submissions")
        except gspread.WorksheetNotFound:
            log_sheet = spreadsheet.add_worksheet("Submissions", rows=1000, cols=3)
            log_sheet.update("A1:C1", [["Question_ID", "Student_ID", "Timestamp"]])

        log_sheet.append_row([question_id, student_id, str(time.time())])
    except Exception:
        pass  # Non-critical — don't block the upload
