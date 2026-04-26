"""
Claude integration for generating plain-English file explanations.

Takes the top-N ranked files and their contents, returns a 2-3 sentence
explanation for each — written for a developer seeing the codebase for the first time.

Prompt caching is applied to the file contents block (the expensive part).
The same repo's contents will be cached for 5 minutes, so repeated requests
(e.g. two users hitting the same repo) cost ~90% less on the second call.
"""

import os
import asyncio
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
TOP_N = 10  # number of files to explain


def _build_file_block(file_path: str, content: str) -> str:
    # Truncate very large files — Claude doesn't need the full 5000 lines
    lines = content.splitlines()
    if len(lines) > 200:
        content = "\n".join(lines[:200]) + f"\n... ({len(lines) - 200} more lines)"
    return f"<file path=\"{file_path}\">\n{content}\n</file>"


async def explain_files(
    repo_full_name: str,
    ranked_files: list[dict],  # [{"path": str, "content": str, "signals": dict}, ...]
) -> list[dict]:
    """
    For each file in ranked_files, generate a 2-3 sentence plain-English explanation.

    ranked_files should already be the top-N, pre-sliced by the caller.

    Returns the same list with an "explanation" key added to each item.
    """
    if not ranked_files:
        return ranked_files

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # Build the file contents block — this gets cached
    files_xml = "\n\n".join(
        _build_file_block(f["path"], f.get("content", "")) for f in ranked_files
    )

    # Build the list of files to explain
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

    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    # Cache the file contents — expensive to re-send, stable within a session
                    {
                        "type": "text",
                        "text": user_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )

    raw = response.content[0].text.strip()

    # Parse JSON response and merge explanations back into ranked_files
    import json
    try:
        explanations = json.loads(raw)
        explanation_map = {e["path"]: e["explanation"] for e in explanations}
    except (json.JSONDecodeError, KeyError):
        # Fallback: if parsing fails, leave explanation blank rather than crashing
        explanation_map = {}

    for f in ranked_files:
        f["explanation"] = explanation_map.get(f["path"], "")

    return ranked_files
