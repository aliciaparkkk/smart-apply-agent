import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from openai import OpenAI

from smart_apply.config import OPENAI_API_KEY, OPENAI_MODEL, ensure_output_dir
from smart_apply.google_docs import create_tailored_google_doc
from smart_apply.job_parser import ParsedJob
from smart_apply.resume_io import read_resume_lines, write_tailored_resume

TAILOR_SYSTEM = """You tailor a resume for a specific job application.

Rules:
- Keep all facts truthful; do not invent employers, degrees, dates, or skills the candidate does not have.
- Emphasize relevant experience and keywords from the job description.
- Improve bullet phrasing for impact and ATS alignment.
- Preserve the same section structure and approximate length.
- Return JSON: {"paragraphs": ["...", "..."]} — one string per resume line in order.
- The paragraphs array length MUST equal the number of input lines exactly.
- Do not split one bullet into multiple lines or merge separate lines.
- Include empty strings "" for blank lines that should remain blank.
- Do not add markdown, numbering prefixes, or section labels that were not in the original."""


@dataclass
class TailorResult:
    title: str
    doc_id: Optional[str] = None
    doc_url: Optional[str] = None
    local_path: Optional[Path] = None
    note: Optional[str] = None
    used_local_fallback: bool = False


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name)
    cleaned = re.sub(r"[\s_-]+", "_", cleaned).strip("_")
    return cleaned[:80] or "resume"


def _doc_title(job: ParsedJob, source_path: Path) -> str:
    company = _sanitize_filename(job.company_name).replace("_", " ")
    title = _sanitize_filename(job.job_title).replace("_", " ")
    stem = source_path.stem[:40]
    return f"Resume — {company} — {title} ({stem})"


def _local_output_path(job: ParsedJob, source_path: Path) -> Path:
    stem = _sanitize_filename(source_path.stem)
    company = _sanitize_filename(job.company_name)
    title = _sanitize_filename(job.job_title)
    return ensure_output_dir() / f"{stem}_{company}_{title}.docx"


def _align_paragraph_counts(
    original: List[str], tailored: List[str]
) -> Tuple[List[str], bool]:
    target = len(original)
    result = [str(p) for p in tailored]

    if len(result) == target:
        return result, False

    if len(result) < target:
        result.extend([""] * (target - len(result)))
        return result, True

    while len(result) > target:
        best_i = min(
            range(len(result) - 1),
            key=lambda i: (
                0 if not result[i].strip() or not result[i + 1].strip() else 1,
                len(result[i]) + len(result[i + 1]),
            ),
        )
        left, right = result[best_i], result[best_i + 1]
        if left.strip() and right.strip():
            merged = f"{left.rstrip()} {right.lstrip()}"
        else:
            merged = (left + right).strip()
        result = result[:best_i] + [merged] + result[best_i + 2 :]

    return result, True


def _call_tailor_model(
    client: OpenAI, job: ParsedJob, original: List[str], strict: bool = False
) -> List[str]:
    numbered = "\n".join(f"{i}: {text}" for i, text in enumerate(original))
    count_rule = (
        f"You MUST return exactly {len(original)} strings in paragraphs — "
        f"no more, no less."
    )
    if strict:
        count_rule += " Do not add or remove lines."

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TAILOR_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Job title: {job.job_title}\n"
                    f"Company: {job.company_name}\n\n"
                    f"Job description:\n{job.description}\n\n"
                    f"Resume lines (index: text):\n{numbered}\n\n"
                    f"{count_rule}"
                ),
            },
        ],
        temperature=0.3 if strict else 0.4,
    )

    data = json.loads(response.choices[0].message.content or "{}")
    return [str(p) for p in data.get("paragraphs", [])]


def get_tailored_paragraphs(
    resume_path: Path,
    job: ParsedJob,
) -> Tuple[List[str], Optional[str]]:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    resume_path = Path(resume_path)
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume not found: {resume_path}")

    original = read_resume_lines(resume_path)
    client = OpenAI(api_key=OPENAI_API_KEY)

    tailored = _call_tailor_model(client, job, original)
    if len(tailored) != len(original):
        tailored = _call_tailor_model(client, job, original, strict=True)

    note = None
    if len(tailored) != len(original):
        model_count = len(tailored)
        tailored, adjusted = _align_paragraph_counts(original, tailored)
        if adjusted:
            note = (
                f"Model returned {model_count} lines but your resume has {len(original)}; "
                "text was merged/padded before saving."
            )
    return tailored, note


def _save_local_docx(
    resume_path: Path, paragraphs: List[str], job: ParsedJob
) -> Path:
    dest = _local_output_path(job, resume_path)
    write_tailored_resume(resume_path, paragraphs, dest)
    return dest


def tailor_resume(
    resume_path: Path,
    job: ParsedJob,
    folder_id: Optional[str] = None,
    share_email: Optional[str] = None,
    source_doc_id: Optional[str] = None,
) -> TailorResult:
    """Tailor resume; prefer Google Doc, fall back to local .docx on Drive errors."""
    paragraphs, note = get_tailored_paragraphs(resume_path, job)
    title = _doc_title(job, resume_path)
    notes = [note] if note else []

    if folder_id and share_email:
        try:
            doc_id, doc_url = create_tailored_google_doc(
                title=title,
                paragraphs=paragraphs,
                folder_id=folder_id,
                share_email=share_email,
                source_doc_id=source_doc_id,
            )
            return TailorResult(
                title=title,
                doc_id=doc_id,
                doc_url=doc_url,
                note=" ".join(n for n in notes if n) or None,
            )
        except Exception as exc:
            notes.append(f"Google Doc failed: {exc}")

    local_path = _save_local_docx(resume_path, paragraphs, job)
    notes.append(
        "Saved tailored resume as .docx on disk. Upload to Google Drive manually, "
        "or set Drive folder ID + email and run again."
    )
    return TailorResult(
        title=title,
        local_path=local_path,
        note=" ".join(notes),
        used_local_fallback=True,
    )
