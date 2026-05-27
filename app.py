"""Streamlit UI for Smart Apply Agent."""

import json
from pathlib import Path
from typing import Optional

import streamlit as st

from smart_apply.agent import AgentContext, run_application_agent
from smart_apply.agent.state import AgentStep
from smart_apply.config import PROJECT_ROOT, RESUME_PATH, ensure_output_dir
from smart_apply.resume_io import SUPPORTED_SUFFIXES


def _resolve_default_resume() -> Optional[Path]:
    if not RESUME_PATH.strip():
        return None
    path = Path(RESUME_PATH)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.exists() else None


def _save_upload(uploaded_file) -> Path:
    safe_name = Path(uploaded_file.name).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Please upload a .docx file.")
    dest = ensure_output_dir() / safe_name
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def _render_agent_step(step: AgentStep) -> None:
    label = f"**{step.tool}**"
    if step.reasoning:
        st.markdown(step.reasoning)
    with st.expander(label, expanded=False):
        if step.arguments:
            st.caption("Arguments")
            st.json(step.arguments)
        st.caption("Result")
        try:
            st.json(step.result)
        except Exception:
            st.code(step.result)


st.set_page_config(page_title="Smart Apply Agent", page_icon="🤖", layout="wide")

st.title("Smart Apply Agent")
st.caption(
    "Agentic AI: an LLM plans and calls tools (parse → inspect → tailor) until the job is done."
)

with st.sidebar:
    st.header("Resume")
    uploaded_resume = st.file_uploader(
        "Upload your resume (.docx)",
        type=["docx"],
        help="Upload your base resume as a .docx file.",
    )

    with st.expander("How is this agentic?"):
        st.markdown(
            """
            Unlike a fixed script, the **LLM chooses tools** in a loop:
            `parse_job_posting` → `inspect_resume` → `tailor_resume` → `finish`.

            Each step is visible below so you can see the reasoning.
            """
        )

job_text = st.text_area(
    "Job posting",
    height=280,
    placeholder="Paste the full job posting here…",
)

col1, col2 = st.columns(2)
with col1:
    run = st.button("Run agent", type="primary", use_container_width=True)
with col2:
    if st.button("Clear", use_container_width=True):
        st.rerun()

if run:
    if not job_text.strip():
        st.error("Paste a job posting first.")
        st.stop()

    default_resume = _resolve_default_resume()

    try:
        if uploaded_resume:
            resume_path = _save_upload(uploaded_resume)
        elif default_resume:
            resume_path = default_resume
        else:
            st.error("Please upload your resume (.docx).")
            st.stop()
    except ValueError as e:
        st.error(str(e))
        st.stop()

    agent_ctx = AgentContext(
        job_text=job_text.strip(),
        resume_path=resume_path,
        from_google_doc=False,
        source_google_doc_id=None,
        log_to_sheets=False,
        share_email="",
        drive_folder_id="",
    )

    st.subheader("Agent activity")
    steps_container = st.container()
    live_steps: list = []

    def on_step(step: AgentStep) -> None:
        live_steps.append(step)
        with steps_container:
            _render_agent_step(step)

    try:
        with st.spinner("Agent is planning and executing tools…"):
            result = run_application_agent(agent_ctx, on_step=on_step)

        ctx = result.context
        st.divider()
        st.subheader("Outcome")

        if ctx.parsed_job:
            c1, c2 = st.columns(2)
            c1.metric("Company", ctx.parsed_job.company_name)
            c2.metric("Title", ctx.parsed_job.job_title)

        if ctx.success:
            st.success(ctx.summary)
        else:
            st.warning(ctx.summary)

        if ctx.tailor_result:
            st.caption(f"**{ctx.tailor_result.title}**")
            if ctx.tailor_result.local_path and ctx.tailor_result.local_path.exists():
                st.download_button(
                    "Download tailored resume (.docx)",
                    data=ctx.tailor_result.local_path.read_bytes(),
                    file_name=ctx.tailor_result.local_path.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

    except Exception as e:
        st.error(f"Agent failed: {e}")