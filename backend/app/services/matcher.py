import json
import logging
from pathlib import Path
from typing import Optional

import anthropic
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from backend.app.models.job_posting import JobPosting, ScoreStatus
from backend.app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")

# Module-level client — can be replaced in tests
anthropic_client = anthropic.AsyncAnthropic()


class DimensionScore(BaseModel):
    score: int
    reasoning: str


class ScoreBreakdown(BaseModel):
    overall_score: int
    low_signal_jd: bool
    dimensions: dict[str, DimensionScore]  # keys: role_fit, stack_fit, seniority_fit, location_fit
    flags: list[str]
    summary: str


SCORE_JOB_POSTING_TOOL = {
    "name": "score_job_posting",
    "description": "Return a structured fit score for a job posting against the candidate profile.",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_score": {"type": "integer", "description": "0-100 overall fit score"},
            "low_signal_jd": {"type": "boolean", "description": "True if JD is fewer than 100 words"},
            "dimensions": {
                "type": "object",
                "properties": {
                    "role_fit": {"type": "object", "properties": {"score": {"type": "integer"}, "reasoning": {"type": "string"}}, "required": ["score", "reasoning"]},
                    "stack_fit": {"type": "object", "properties": {"score": {"type": "integer"}, "reasoning": {"type": "string"}}, "required": ["score", "reasoning"]},
                    "seniority_fit": {"type": "object", "properties": {"score": {"type": "integer"}, "reasoning": {"type": "string"}}, "required": ["score", "reasoning"]},
                    "location_fit": {"type": "object", "properties": {"score": {"type": "integer"}, "reasoning": {"type": "string"}}, "required": ["score", "reasoning"]},
                },
                "required": ["role_fit", "stack_fit", "seniority_fit", "location_fit"]
            },
            "flags": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"}
        },
        "required": ["overall_score", "low_signal_jd", "dimensions", "flags", "summary"]
    }
}


async def score_job_posting(job: JobPosting, profile: UserProfile, session: Session) -> None:
    system_template = _load_prompt("matcher_system.md")
    user_template = _load_prompt("matcher_user.md")

    system_prompt = system_template.replace("{cv_markdown}", profile.cv_markdown).replace("{preferences}", profile.preferences)
    user_prompt = user_template.replace("{job_description}", job.description)

    messages = [{"role": "user", "content": user_prompt}]

    last_exc = None
    response = None
    for attempt in range(2):
        try:
            response = await anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                tools=[SCORE_JOB_POSTING_TOOL],
                tool_choice={"type": "tool", "name": "score_job_posting"},
                messages=messages,
            )
            last_exc = None
            break
        except anthropic.APIError as e:
            last_exc = e
            logger.warning("Anthropic API error on attempt %d: %s", attempt + 1, e)

    if last_exc is not None:
        logger.error("Scoring failed after 2 attempts for job %s", job.id)
        job.score_status = ScoreStatus.error
        session.add(job)
        session.commit()
        return

    # Extract tool_use block
    tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use_block is None:
        logger.error("No tool_use block in response for job %s", job.id)
        job.score_status = ScoreStatus.error
        session.add(job)
        session.commit()
        return

    try:
        breakdown = ScoreBreakdown(**tool_use_block.input)
    except (ValidationError, Exception) as e:
        logger.error("ScoreBreakdown validation failed for job %s: %s", job.id, e)
        job.score_status = ScoreStatus.error
        session.add(job)
        session.commit()
        return

    # Defensive cap
    if breakdown.low_signal_jd and breakdown.overall_score > 70:
        breakdown.overall_score = 70

    job.overall_score = breakdown.overall_score
    job.score_breakdown = breakdown.model_dump_json()
    job.score_status = ScoreStatus.scored
    session.add(job)
    session.commit()
