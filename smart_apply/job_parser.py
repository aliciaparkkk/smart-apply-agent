import json
from dataclasses import dataclass

from openai import OpenAI

from smart_apply.config import OPENAI_API_KEY, OPENAI_MODEL

PARSE_SYSTEM = """You extract structured job posting data from raw text.
Return JSON only with keys: company_name, job_title, description.
- company_name: hiring company (best guess if unclear)
- job_title: role title
- description: full job description, cleaned but complete
If a field is missing, use "Unknown" for company/title or summarize what is present for description."""


@dataclass
class ParsedJob:
    company_name: str
    job_title: str
    description: str


def parse_job_posting(raw_text: str) -> ParsedJob:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PARSE_SYSTEM},
            {
                "role": "user",
                "content": f"Parse this job posting:\n\n{raw_text.strip()}",
            },
        ],
        temperature=0.2,
    )

    data = json.loads(response.choices[0].message.content or "{}")
    return ParsedJob(
        company_name=str(data.get("company_name", "Unknown")).strip(),
        job_title=str(data.get("job_title", "Unknown")).strip(),
        description=str(data.get("description", raw_text.strip())).strip(),
    )
