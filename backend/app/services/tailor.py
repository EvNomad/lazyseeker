import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import anthropic
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

from backend.app.models.job_posting import JobPosting
from backend.app.models.suggestion import Suggestion, SuggestionStatus
from backend.app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")

anthropic_client = anthropic.AsyncAnthropic()


class TailorError(Exception):
    pass


class SuggestionInput(BaseModel):
    section: str
    original: str
    suggested: str
    rationale: str


GENERATE_SUGGESTIONS_TOOL = {
    "name": "generate_suggestions",
    "description": "Return a list of CV improvement suggestions for the job posting.",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string"},
                        "original": {"type": "string"},
                        "suggested": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["section", "original", "suggested", "rationale"],
                },
            }
        },
        "required": ["suggestions"],
    },
}


def cv_version_for_profile(profile: UserProfile) -> str:
    return hashlib.sha256(profile.cv_markdown.encode()).hexdigest()


async def generate_suggestions(
    job: JobPosting, profile: UserProfile, session: Session
) -> list[Suggestion]:
    cv_version = cv_version_for_profile(profile)

    # Delete existing pending suggestions for this job; preserve approved/rejected
    existing = session.exec(
        select(Suggestion).where(Suggestion.job_id == job.id)
    ).all()
    for s in existing:
        if s.status == SuggestionStatus.pending:
            session.delete(s)
    session.commit()

    system_template = _load_prompt("tailor_system.md")
    user_template = _load_prompt("tailor_user.md")
    system_prompt = system_template.replace("{cv_markdown}", profile.cv_markdown)
    user_prompt = user_template.replace("{job_description}", job.description)

    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            tools=[GENERATE_SUGGESTIONS_TOOL],
            tool_choice={"type": "tool", "name": "generate_suggestions"},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        raise TailorError(f"Anthropic API error: {e}") from e

    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use_block is None:
        raise TailorError("No tool_use block in response")

    try:
        raw_suggestions = tool_use_block.input.get("suggestions", [])
        parsed = [SuggestionInput(**s) for s in raw_suggestions]
    except (ValidationError, Exception) as e:
        raise TailorError(f"Invalid suggestion format: {e}") from e

    # Enforce max 6
    if len(parsed) > 6:
        logger.warning("Claude returned %d suggestions; truncating to 6", len(parsed))
        parsed = parsed[:6]

    suggestions = [
        Suggestion(
            job_id=job.id,
            section=s.section,
            original=s.original,
            suggested=s.suggested,
            rationale=s.rationale,
            cv_version=cv_version,
            status=SuggestionStatus.pending,
        )
        for s in parsed
    ]
    for s in suggestions:
        session.add(s)
    session.commit()
    for s in suggestions:
        session.refresh(s)
    return suggestions


def assemble_tailored_cv(cv_markdown: str, suggestions: list[Suggestion]) -> str:
    result = cv_markdown
    unmatched = []
    for s in suggestions:
        if s.original in result:
            result = result.replace(s.original, s.suggested, 1)
        else:
            unmatched.append(s)
    if unmatched:
        result += "\n\n## Unmatched Suggestions\n"
        for s in unmatched:
            result += f"\n**{s.section}**: {s.suggested}\n> {s.rationale}\n"
    return result
