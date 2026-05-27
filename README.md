# Smart Apply Agent

**Agentic AI** for job applications: an LLM plans and calls tools to parse a posting, tailor your resume, and log to Google Sheets.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the interview-style design breakdown.

## Setup

1. **Python 3.10+** and a virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Environment** — copy `.env.example` to `.env` and set:

- `OPENAI_API_KEY` — from [OpenAI](https://platform.openai.com/api-keys)
- `RESUME_PATH` — optional path to a default resume (any filename; `.docx` or `.pdf`)
- `GOOGLE_CREDENTIALS_PATH` — path to a Google Cloud **service account** JSON key (default: `credentials.json`)
- `GOOGLE_SHARE_EMAIL` — optional; your Gmail/Google address to receive the auto-created sheet

3. **Google** (Sheets log + optional Google Doc resume)

- Create a project in [Google Cloud Console](https://console.cloud.google.com/)
- Enable **Google Sheets API**, **Google Drive API**, and **Google Docs API**
- Create a service account → download JSON → save as `credentials.json`
- In **your** Google Drive, create a folder (e.g. `Smart Apply`) and share it with the service account email as **Editor**
- Copy the folder ID from the URL into `GOOGLE_DRIVE_FOLDER_ID` (or the sidebar field)
- On first **Apply**, a spreadsheet is created **inside that folder** (uses your storage, not the service account’s)
- For **best resume formatting**, use **Google Doc link** in the app (share the doc with the service account too). PDF uploads lose layout; `.docx` is also good.

4. **Resume** — upload any `.docx` or `.pdf` in the app, or optionally set `RESUME_PATH`.

## Run

```bash
streamlit run app.py
```

## Flow (agentic)

1. You paste a job posting and provide a resume
2. Click **Run agent** — the LLM loops: choose tool → execute → observe
3. Typical plan: `parse_job_posting` → `inspect_resume` → `tailor_resume` → `log_application` → `finish`
4. Tool steps appear in the UI; open the tailored **Google Doc** link when done

## Project layout

```
smart-apply-agent/
├── app.py                 # Streamlit UI
├── smart_apply/
│   ├── agent/             # Agent loop + tool definitions
│   ├── job_parser.py      # Parse posting (tool backend)
│   ├── resume_tailor.py   # Tailor resume (tool backend)
│   └── sheets_logger.py   # Google Sheets (tool backend)
├── ARCHITECTURE.md        # Interview guide
├── output/                # Tailored resumes (gitignored)
├── your-resume.pdf        # Optional default resume (any name)
└── credentials.json       # Google service account (you add this)
```
