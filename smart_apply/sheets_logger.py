from datetime import datetime
from pathlib import Path
from typing import Optional

import gspread
from gspread.exceptions import APIError

from smart_apply.config import (
    DEFAULT_SPREADSHEET_TITLE,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_SHARE_EMAIL,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_WORKSHEET,
    SHEET_HEADERS,
    SHEET_ID_FILE,
)
from smart_apply.google_auth import get_credentials, get_service_account_email
from smart_apply.job_parser import ParsedJob

DRIVE_QUOTA_HELP = """
Google blocked sheet creation because the service account has no Drive storage.

**Fix (one-time):**
1. In Google Drive, create a folder (e.g. `Smart Apply`).
2. Share that folder with **{service_email}** as **Editor**.
3. Copy the folder ID from the URL: `drive.google.com/drive/folders/FOLDER_ID`
4. Paste it in the sidebar **Drive folder ID** field (or set `GOOGLE_DRIVE_FOLDER_ID` in `.env`).
5. Delete `.google_sheet_id` in the project folder if it exists, then Apply again.
""".strip()


def _get_client() -> gspread.Client:
    return gspread.authorize(get_credentials())


def _load_saved_sheet_id() -> Optional[str]:
    if GOOGLE_SHEET_ID.strip():
        return GOOGLE_SHEET_ID.strip()
    if SHEET_ID_FILE.exists():
        saved = SHEET_ID_FILE.read_text().strip()
        if saved:
            return saved
    return None


def _save_sheet_id(sheet_id: str) -> None:
    SHEET_ID_FILE.write_text(sheet_id)


def spreadsheet_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"


def get_application_log_url() -> Optional[str]:
    sheet_id = _load_saved_sheet_id()
    return spreadsheet_url(sheet_id) if sheet_id else None


def _share_with_user(spreadsheet: gspread.Spreadsheet, email: str) -> None:
    email = email.strip()
    if not email:
        return
    spreadsheet.share(email, perm_type="user", role="writer", notify=True)


def _setup_worksheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        worksheet = spreadsheet.worksheet(GOOGLE_SHEET_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=GOOGLE_SHEET_WORKSHEET, rows=1000, cols=len(SHEET_HEADERS)
        )

    existing = worksheet.row_values(1)
    if existing != SHEET_HEADERS:
        worksheet.update([SHEET_HEADERS], range_name="A1")

    return worksheet


def _create_spreadsheet(
    client: gspread.Client, folder_id: Optional[str]
) -> gspread.Spreadsheet:
    folder_id = (folder_id or GOOGLE_DRIVE_FOLDER_ID or "").strip()
    if not folder_id:
        email = get_service_account_email() or "your-service-account@....iam.gserviceaccount.com"
        raise ValueError(
            "Drive folder ID is required to create the application log spreadsheet.\n\n"
            + DRIVE_QUOTA_HELP.format(service_email=email)
        )
    try:
        return client.create(DEFAULT_SPREADSHEET_TITLE, folder_id=folder_id)
    except APIError as exc:
        message = str(exc).lower()
        if "storage quota" in message or "quota" in message:
            email = get_service_account_email()
            raise ValueError(DRIVE_QUOTA_HELP.format(service_email=email)) from exc
        raise


def _ensure_spreadsheet(
    client: gspread.Client,
    share_email: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> tuple[gspread.Spreadsheet, bool]:
    """Return (spreadsheet, created_this_call)."""
    email = (share_email or GOOGLE_SHARE_EMAIL or "").strip()
    saved_id = _load_saved_sheet_id()

    if saved_id:
        try:
            spreadsheet = client.open_by_key(saved_id)
            return spreadsheet, False
        except gspread.SpreadsheetNotFound:
            pass

    spreadsheet = _create_spreadsheet(client, folder_id)
    _save_sheet_id(spreadsheet.id)

    worksheet = spreadsheet.sheet1
    if worksheet.title != GOOGLE_SHEET_WORKSHEET:
        worksheet.update_title(GOOGLE_SHEET_WORKSHEET)

    _share_with_user(spreadsheet, email)
    return spreadsheet, True


def log_application(
    job: ParsedJob,
    resume_doc: str,
    share_email: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> str:
    """Append a row and return the spreadsheet URL."""
    client = _get_client()
    spreadsheet, created = _ensure_spreadsheet(
        client, share_email=share_email, folder_id=folder_id
    )

    if not created and share_email:
        _share_with_user(spreadsheet, share_email)

    worksheet = _setup_worksheet(spreadsheet)

    description = job.description
    if len(description) > 500:
        description = description[:497] + "..."

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        job.company_name,
        job.job_title,
        resume_doc,
        description,
    ]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
    return spreadsheet_url(spreadsheet.id)
