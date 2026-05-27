import io
import re
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from smart_apply.config import ensure_output_dir
from smart_apply.google_auth import get_credentials

DOC_URL_PATTERNS = (
    r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)",
    r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
)


def parse_google_file_id(url: str) -> str:
    url = url.strip()
    for pattern in DOC_URL_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(
        "Could not read a Google Doc/Drive file ID from that URL. "
        "Use a link like https://docs.google.com/document/d/.../edit"
    )


def export_google_doc_to_docx(url: str, dest_name: str = "google_resume.docx") -> Path:
    """Export a shared Google Doc to .docx (keeps fonts, spacing, styles)."""
    file_id = parse_google_file_id(url)
    dest = ensure_output_dir() / dest_name

    drive = build("drive", "v3", credentials=get_credentials(), cache_discovery=False)
    request = drive.files().export_media(
        fileId=file_id,
        mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    dest.write_bytes(buffer.getvalue())
    return dest
