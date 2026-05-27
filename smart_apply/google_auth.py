import json
from pathlib import Path

from google.oauth2.service_account import Credentials

from smart_apply.config import GOOGLE_CREDENTIALS_PATH, PROJECT_ROOT

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def credentials_path() -> Path:
    path = Path(GOOGLE_CREDENTIALS_PATH)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def get_credentials() -> Credentials:
    path = credentials_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Google credentials not found at {path}. "
            "Save your service account JSON as credentials.json."
        )
    return Credentials.from_service_account_file(str(path), scopes=SCOPES)


def get_service_account_email() -> str:
    path = credentials_path()
    data = json.loads(path.read_text())
    return str(data.get("client_email", ""))
