import json
from typing import Callable, List, Optional

from openai import OpenAI

from smart_apply.agent.state import AgentContext, AgentResult, AgentStep
from smart_apply.agent.tools import TOOL_SCHEMAS, execute_tool
from smart_apply.config import OPENAI_API_KEY, OPENAI_MODEL

MAX_AGENT_STEPS = 10

AGENT_SYSTEM = """You are Smart Apply Agent — an autonomous assistant that helps a user apply to one job.

You achieve the goal by calling tools in a loop. After each tool result, decide the next best action.

## Goal
1. Parse the job posting
2. Inspect the resume (recommended)
3. Tailor the resume to the job
4. Log to Google Sheets if log_to_sheets is true
5. Call finish with a clear summary (include the Google Doc link when tailored)

## Rules
- Use one tool per turn. Do not skip straight to finish unless work is done or impossible.
- Never fabricate resume content; tailoring is handled by tailor_resume.
- If a tool returns an error, try to recover (e.g. parse before tailor) or finish with success=false.
- tailor_resume may save a local .docx if Google Doc creation fails; that still counts as success.
- If log_to_sheets is false, skip log_application and say so in the summary.
- Be concise in your reasoning before each tool call.

## Context (user settings)
You will receive JSON context with job_text, resume file info, log_to_sheets, and Google settings."""


def _build_user_context(ctx: AgentContext) -> str:
    return json.dumps(
        {
            "resume_file": ctx.resume_path.name,
            "resume_format": ctx.resume_path.suffix.lower(),
            "from_google_doc": ctx.from_google_doc,
            "source_google_doc_id": ctx.source_google_doc_id,
            "log_to_sheets": ctx.log_to_sheets,
            "has_share_email": bool(ctx.share_email.strip()),
            "has_drive_folder_id": bool(ctx.drive_folder_id.strip()),
            "job_posting_preview": ctx.job_text[:500],
        },
        indent=2,
    )


def run_application_agent(
    ctx: AgentContext,
    on_step: Optional[Callable[[AgentStep], None]] = None,
) -> AgentResult:
    """
    Run the agentic loop: LLM chooses tools until finish.

    on_step: optional callback(AgentStep) for live UI updates.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    messages: List[dict] = [
        {"role": "system", "content": AGENT_SYSTEM},
        {
            "role": "user",
            "content": (
                "Process this job application. Here is the session context:\n\n"
                + _build_user_context(ctx)
                + "\n\nFull job posting:\n"
                + ctx.job_text
            ),
        },
    ]

    steps: List[AgentStep] = []

    for _ in range(MAX_AGENT_STEPS):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            # Nudge model to use tools
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "Continuing…",
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": "Use the available tools. Call finish when done.",
                }
            )
            continue

        messages.append(message.model_dump(exclude_none=True))

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            result = execute_tool(ctx, name, args)
            step = AgentStep(
                tool=name,
                reasoning=message.content,
                arguments=args,
                result=result,
            )
            steps.append(step)
            if on_step:
                on_step(step)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

            if name == "finish" or ctx.finished:
                return AgentResult(context=ctx, steps=steps)

    ctx.finished = True
    ctx.success = bool(ctx.tailor_result)
    ctx.summary = (
        "Agent reached max steps. "
        + ("Resume was tailored." if ctx.tailor_result else "Resume was not tailored.")
    )
    return AgentResult(context=ctx, steps=steps)
