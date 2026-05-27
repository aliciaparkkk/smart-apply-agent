import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Optional: path to a default resume on disk (any filename, .docx or .pdf)
RESUME_PATH = os.getenv("RESUME_PATH", "")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
# Optional override; otherwise a sheet is created on first log and saved to .google_sheet_id
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SHEET_WORKSHEET = os.getenv("GOOGLE_SHEET_WORKSHEET", "Applications")
GOOGLE_SHARE_EMAIL = os.getenv("GOOGLE_SHARE_EMAIL", "")
# Folder in YOUR Drive shared with the service account (avoids quota errors)
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
DEFAULT_SPREADSHEET_TITLE = os.getenv(
    "GOOGLE_SPREADSHEET_TITLE", "Smart Apply — Job Applications"
)
SHEET_ID_FILE = PROJECT_ROOT / ".google_sheet_id"

SHEET_HEADERS = [
    "Date",
    "Company",
    "Job Title",
    "Resume Doc",
    "Description",
]


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
