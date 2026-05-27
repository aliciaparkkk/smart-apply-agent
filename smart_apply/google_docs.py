"""Create tailored Google Docs via Drive + Docs API."""

from typing import List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from smart_apply.google_auth import get_credentials, get_service_account_email

DOC_MIME = "application/vnd.google-apps.document"

DRIVE_QUOTA_HELP = """
Google Drive blocked creating the doc (service account storage limit).

**Fix:** Create a folder in your Drive, share it with **{service_email}** as Editor,
paste the folder ID in the sidebar, and enter your Gmail. The app will also save a
local .docx backup if Google Doc creation still fails.
""".strip()


def google_doc_url(document_id: str) -> str:
    return f"https://docs.google.com/document/d/{document_id}/edit"


def _require_drive_setup(folder_id: Optional[str], share_email: Optional[str]) -> str:
    folder_id = (folder_id or "").strip()
    share_email = (share_email or "").strip()
    if not folder_id:
        email = get_service_account_email() or "your-service-account@....iam.gserviceaccount.com"
        raise ValueError(
            "Drive folder ID is required.\n\n"
            + DRIVE_QUOTA_HELP.format(service_email=email)
        )
    if not share_email:
        raise ValueError(
            "Your Google email is required so the tailored doc is shared with you."
        )
    return folder_id


def _docs_and_drive():
    creds = get_credentials()
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return docs, drive


def _drive_execute(drive, request):
    return request.execute()


def _share_writer(drive, file_id: str, email: str) -> None:
    drive.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": "writer", "emailAddress": email.strip()},
        sendNotificationEmail=True,
        supportsAllDrives=True,
    ).execute()


def _create_doc_in_folder(drive, title: str, folder_id: str) -> str:
    created = (
        drive.files()
        .create(
            body={
                "name": title,
                "mimeType": DOC_MIME,
                "parents": [folder_id],
            },
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    return created["id"]


def _replace_body_text(docs, document_id: str, paragraphs: List[str]) -> None:
    """Replace entire document body with tailored lines (most reliable)."""
    document = docs.documents().get(documentId=document_id).execute()
    content = document.get("body", {}).get("content", [])
    if not content:
        raise ValueError("Google Doc has no body content.")

    end_index = content[-1].get("endIndex", 1)
    delete_end = max(1, end_index - 1)
    text = "\n".join(paragraphs)
    if text and not text.endswith("\n"):
        text += "\n"

    requests = []
    if delete_end > 1:
        requests.append(
            {
                "deleteContentRange": {
                    "range": {"startIndex": 1, "endIndex": delete_end},
                }
            }
        )
    if text:
        requests.append(
            {"insertText": {"location": {"index": 1}, "text": text}}
        )

    if requests:
        docs.documents().batchUpdate(
            documentId=document_id,
            body={"requests": requests},
        ).execute()


def create_tailored_google_doc(
    title: str,
    paragraphs: List[str],
    folder_id: Optional[str] = None,
    share_email: Optional[str] = None,
    source_doc_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Create a tailored Google Doc in the user's shared Drive folder.

    Uses create-in-folder + full body replace (works with personal Gmail + service accounts).
    source_doc_id is only used for titling context; we do not copy (copy often hits SA quota).
    """
    del source_doc_id  # reserved for future copy-based formatting
    folder_id = _require_drive_setup(folder_id, share_email)
    share_email = share_email.strip()

    docs, drive = _docs_and_drive()

    try:
        doc_id = _create_doc_in_folder(drive, title, folder_id)
        _replace_body_text(docs, doc_id, list(paragraphs))
        _share_writer(drive, doc_id, share_email)
        return doc_id, google_doc_url(doc_id)

    except HttpError as exc:
        message = str(exc).lower()
        if "storage quota" in message or "quota" in message:
            email = get_service_account_email()
            raise ValueError(DRIVE_QUOTA_HELP.format(service_email=email)) from exc
        raise ValueError(f"Google Docs API error: {exc}") from exc
