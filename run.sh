#!/usr/bin/env bash
# Always use the project venv (avoids "No module named 'openai'" from conda streamlit)
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt -q
exec streamlit run app.py
