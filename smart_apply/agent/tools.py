import json
from typing import Any, Callable, Dict

from smart_apply.agent.state import AgentContext
from smart_apply.job_parser import parse_job_posting
from smart_apply.resume_io import read_resume_lines
from smart_apply.resume_tailor import tailor_resume
from smart_apply.sheets_logger import log_application

# OpenAI function-calling schemas
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "parse_job_posting",
            "description": (
                "Parse the raw job posting into company name, job title, and description. "
                "Call this first if not yet parsed."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_resume",
            "description": (
                "Inspect the resume file: format, line count, and formatting expectations. "
                "Use before tailoring to choose the right expectations."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tailor_resume",
            "description": (
                "Tailor the resume to the parsed job and create a new Google Doc in the "
                "user's shared Drive folder. Requires parse_job_posting, drive_folder_id, "
                "and share_email in context. Returns a Google Doc edit link."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_application",
            "description": (
                "Append this application to the Google Sheets log. "
                "Requires parse_job_posting and tailor_resume. "
                "Only call when log_to_sheets is enabled."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Mark the workflow complete and return a summary to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Short summary of what was accomplished.",
                    },
                    "success": {
                        "type": "boolean",
                        "description": "Whether the application workflow succeeded.",
                    },
                },
                "required": ["summary", "success"],
            },
        },
    },
]


def _tool_parse_job(ctx: AgentContext, _: Dict[str, Any]) -> str:
    if ctx.parsed_job:
        job = ctx.parsed_job
        return json.dumps(
            {
                "status": "already_parsed",
                "company_name": job.company_name,
                "job_title": job.job_title,
                "description_preview": job.description[:300],
            }
        )
    job = parse_job_posting(ctx.job_text)
    ctx.parsed_job = job
    return json.dumps(
        {
            "status": "parsed",
            "company_name": job.company_name,
            "job_title": job.job_title,
            "description_length": len(job.description),
        }
    )


def _tool_inspect_resume(ctx: AgentContext, _: Dict[str, Any]) -> str:
    path = ctx.resume_path
    suffix = path.suffix.lower()
    lines = read_resume_lines(path)
    format_quality = "high"
    notes = []
    if ctx.from_google_doc:
        notes.append(
            "Source is a Google Doc; output will copy that doc and update text (format preserved)."
        )
    elif suffix == ".pdf":
        format_quality = "low"
        notes.append("PDF source: output Google Doc will be plain text layout.")
    elif suffix == ".docx":
        notes.append("DOCX source: output will be a new Google Doc with tailored text.")
    return json.dumps(
        {
            "file": path.name,
            "format": suffix,
            "line_count": len(lines),
            "format_quality": format_quality,
            "notes": notes,
        }
    )


def _tool_tailor(ctx: AgentContext, _: Dict[str, Any]) -> str:
    if not ctx.parsed_job:
        return json.dumps({"error": "Call parse_job_posting before tailor_resume."})
    result = tailor_resume(
        ctx.resume_path,
        ctx.parsed_job,
        folder_id=ctx.drive_folder_id or None,
        share_email=ctx.share_email or None,
        source_doc_id=ctx.source_google_doc_id,
    )
    ctx.tailor_result = result
    payload = {
        "status": "tailored",
        "google_doc_title": result.title,
        "google_doc_url": result.doc_url,
        "google_doc_id": result.doc_id,
        "local_path": str(result.local_path) if result.local_path else None,
        "used_local_fallback": result.used_local_fallback,
    }
    if result.note:
        payload["warning"] = result.note
    return json.dumps(payload)


def _tool_log(ctx: AgentContext, _: Dict[str, Any]) -> str:
    if not ctx.log_to_sheets:
        return json.dumps({"skipped": True, "reason": "log_to_sheets is disabled."})
    if not ctx.parsed_job or not ctx.tailor_result:
        return json.dumps(
            {"error": "Need parse_job_posting and tailor_resume before logging."}
        )
    resume_label = (
        ctx.tailor_result.doc_url
        or (str(ctx.tailor_result.local_path.name) if ctx.tailor_result.local_path else "")
    )
    url = log_application(
        ctx.parsed_job,
        resume_label,
        share_email=ctx.share_email or None,
        folder_id=ctx.drive_folder_id or None,
    )
    ctx.sheet_url = url
    return json.dumps({"status": "logged", "spreadsheet_url": url})


def _tool_finish(ctx: AgentContext, args: Dict[str, Any]) -> str:
    ctx.finished = True
    ctx.success = bool(args.get("success", True))
    ctx.summary = str(args.get("summary", "Done."))
    return json.dumps({"status": "finished", "summary": ctx.summary})


TOOL_HANDLERS: Dict[str, Callable[[AgentContext, Dict[str, Any]], str]] = {
    "parse_job_posting": _tool_parse_job,
    "inspect_resume": _tool_inspect_resume,
    "tailor_resume": _tool_tailor,
    "log_application": _tool_log,
    "finish": _tool_finish,
}


def execute_tool(ctx: AgentContext, name: str, arguments: Dict[str, Any]) -> str:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        return handler(ctx, arguments)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
