# Agentic architecture (interview guide)

## What makes this agentic?

| Fixed pipeline (before) | Agentic (now) |
|-------------------------|---------------|
| Same steps every run | LLM **decides** which tool to call next |
| No observation loop | **Tool result → reason → next action** |
| Hard-coded error handling | Agent can **recover** (e.g. parse before tailor) |
| Opaque to the user | **Visible tool trace** in the UI |

## Loop (ReAct + function calling)

```
User clicks "Run agent"
        ↓
┌───────────────────────────────────────┐
│  LLM (system prompt + context)        │
│  Chooses one or more tool calls       │
└───────────────────────────────────────┘
        ↓
┌───────────────────────────────────────┐
│  Execute tool (Python)                │
│  parse | inspect | tailor | log | finish │
└───────────────────────────────────────┘
        ↓
   Tool result appended to conversation
        ↓
   Repeat until `finish` or max steps (10)
```

## Tools (`smart_apply/agent/tools.py`)

| Tool | Purpose |
|------|---------|
| `parse_job_posting` | Structured company / title / description |
| `inspect_resume` | Format, line count, PDF vs Docx guidance |
| `tailor_resume` | LLM rewrites resume; preserves docx layout |
| `log_application` | Append row to Google Sheets |
| `finish` | End run with summary |

## Key files

- `smart_apply/agent/agent.py` — orchestration loop, OpenAI tool calls
- `smart_apply/agent/tools.py` — tool schemas + implementations
- `smart_apply/agent/state.py` — shared `AgentContext` across steps
- `app.py` — Streamlit UI with live step trace

## Interview talking points

1. **Autonomy with guardrails** — The model plans, but tools enforce real actions (file I/O, APIs).
2. **Observability** — Every tool call is logged for debugging and demos.
3. **Separation of concerns** — Agent orchestrates; `job_parser`, `resume_tailor`, `sheets_logger` stay testable.
4. **Tradeoffs** — More latency/cost than a script; worth it when steps may vary or fail unpredictably.

## Possible extensions

- Human-in-the-loop tool (`ask_user`) before submitting
- Retry tool with different strategy after PDF inspect
- Multi-job batch agent with memory across applications
