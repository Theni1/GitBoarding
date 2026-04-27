"""
OpenAI integration for generating plain-English file explanations.

Takes the top-N ranked files and their contents, returns a 2-3 sentence
explanation for each — written for a developer seeing the codebase for the first time.
"""

import os
import json
from openai import AsyncOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"
TOP_N = 10


async def analyze_architecture(repo_full_name: str, config_files: dict[str, str]) -> dict | None:
    """
    Given a dict of {filename: content} for config files found in the repo,
    ask GPT to infer the system architecture and return structured JSON.
    """
    if not config_files:
        return None

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    files_text = "\n\n".join(
        f"=== {path} ===\n{content[:800]}" for path, content in config_files.items()
    )

    prompt = f"""You are analyzing the GitHub repo: {repo_full_name}

Here are the config/manifest files found in the repo:

{files_text}

Based on these files, identify the system architecture. Group related components into logical sections.

Return ONLY a JSON object in this exact format:
{{
  "groups": [
    {{
      "id": "client",
      "label": "CLIENT",
      "col": 0,
      "row": 0,
      "components": [
        {{"id": "web", "label": "Next.js", "type": "frontend"}},
        {{"id": "styles", "label": "Tailwind", "type": "frontend"}}
      ]
    }},
    {{
      "id": "server",
      "label": "SERVER",
      "col": 1,
      "row": 0,
      "components": [
        {{"id": "api", "label": "FastAPI", "type": "backend"}}
      ]
    }},
    {{
      "id": "data",
      "label": "DATA",
      "col": 2,
      "row": 0,
      "components": [
        {{"id": "db", "label": "PostgreSQL", "type": "database"}},
        {{"id": "cache", "label": "Redis", "type": "cache"}}
      ]
    }}
  ],
  "edges": [
    {{"from": "web", "to": "api", "label": "HTTP"}},
    {{"from": "api", "to": "db"}}
  ]
}}

Rules:
- Group components that belong together (e.g. all frontend tech in one group, all backend in another).
- col/row are 0-indexed grid positions for arranging groups left-to-right, top-to-bottom.
- Component types: frontend, backend, database, cache, queue, devops, ml, other.
- Use short names (e.g. "Next.js", "FastAPI", "Redis", "Docker", "PyTorch").
- edges connect component ids (not group ids).
- Only include what is clearly present in the config files.
- If no clear architecture, return {{"groups": [], "edges": []}}.
- Return only the JSON, nothing else."""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception:
        return None


def _build_file_block(file_path: str, content: str) -> str:
    lines = content.splitlines()
    if len(lines) > 200:
        content = "\n".join(lines[:200]) + f"\n... ({len(lines) - 200} more lines)"
    return f"<file path=\"{file_path}\">\n{content}\n</file>"


async def explain_files(
    repo_full_name: str,
    ranked_files: list[dict],
) -> list[dict]:
    if not ranked_files:
        return ranked_files

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    files_xml = "\n\n".join(
        _build_file_block(f["path"], f.get("content", "")) for f in ranked_files
    )
    file_list = "\n".join(f"{i+1}. {f['path']}" for i, f in enumerate(ranked_files))

    system_prompt = (
        "You are a senior engineer helping a new developer onboard onto a codebase. "
        "Your explanations are concise, specific, and written for someone who is smart "
        "but unfamiliar with this repo. Never explain what a language feature does — "
        "explain what THIS file does and why it matters for understanding the codebase."
    )

    user_prompt = f"""I'm onboarding onto the GitHub repo: {repo_full_name}

Here are the most important files to read first, ranked by our model:

{file_list}

Here are the file contents:

<files>
{files_xml}
</files>

For each file, write exactly 2-3 sentences explaining:
1. What this file does
2. Why a new contributor needs to understand it

Format your response as a JSON array:
[
  {{"path": "file/path.py", "explanation": "..."}},
  ...
]

Only output the JSON array, nothing else."""

    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            explanations = parsed
        else:
            # Find the first value that's a list
            explanations = next((v for v in parsed.values() if isinstance(v, list)), [])
        explanation_map = {e["path"]: e["explanation"] for e in explanations if isinstance(e, dict)}
    except (json.JSONDecodeError, KeyError):
        explanation_map = {}

    for f in ranked_files:
        f["explanation"] = explanation_map.get(f["path"], "")

    return ranked_files
