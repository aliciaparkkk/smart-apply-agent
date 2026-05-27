from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from smart_apply.job_parser import ParsedJob
from smart_apply.resume_tailor import TailorResult


@dataclass
class AgentStep:
    """One tool invocation in the agent loop (visible in the UI for demos)."""

    tool: str
    reasoning: Optional[str]
    arguments: Dict[str, Any]
    result: str


@dataclass
class AgentContext:
    """Mutable state shared across tool calls."""

    job_text: str
    resume_path: Path
    from_google_doc: bool
    log_to_sheets: bool
    share_email: str
    drive_folder_id: str
    source_google_doc_id: Optional[str] = None
    parsed_job: Optional[ParsedJob] = None
    tailor_result: Optional[TailorResult] = None
    sheet_url: Optional[str] = None
    finished: bool = False
    success: bool = False
    summary: str = ""


@dataclass
class AgentResult:
    context: AgentContext
    steps: List[AgentStep] = field(default_factory=list)
