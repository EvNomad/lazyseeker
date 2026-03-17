import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import anthropic

from backend.app.services.matcher import score_job_posting, ScoreBreakdown
from backend.app.models.job_posting import JobPosting, ScoreStatus, Language, Source
from backend.app.models.user_profile import UserProfile
from backend.tests.fixtures.seed import make_company, make_job_posting, make_user_profile


def make_tool_response(breakdown_dict: dict):
    """Build a fake anthropic Message with a tool_use content block."""
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.input = breakdown_dict
    msg = MagicMock()
    msg.content = [tool_use]
    return msg


VALID_BREAKDOWN = {
    "overall_score": 82,
    "low_signal_jd": False,
    "dimensions": {
        "role_fit": {"score": 85, "reasoning": "Strong backend match"},
        "stack_fit": {"score": 80, "reasoning": "Python and FastAPI match"},
        "seniority_fit": {"score": 90, "reasoning": "Senior level aligns"},
        "location_fit": {"score": 70, "reasoning": "Remote friendly"},
    },
    "flags": [],
    "summary": "Good match overall. Strong backend experience. Some gaps in required certifications.",
}


@pytest.mark.asyncio
async def test_happy_path_scored(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=AsyncMock(return_value=make_tool_response(VALID_BREAKDOWN)),
    ):
        await score_job_posting(job, profile, session)

    assert job.score_status == ScoreStatus.scored
    assert job.overall_score == 82
    breakdown = json.loads(job.score_breakdown)
    assert set(breakdown["dimensions"].keys()) == {"role_fit", "stack_fit", "seniority_fit", "location_fit"}


@pytest.mark.asyncio
async def test_short_jd_cap_at_70(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    overridden = {**VALID_BREAKDOWN, "low_signal_jd": True, "overall_score": 85}

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=AsyncMock(return_value=make_tool_response(overridden)),
    ):
        await score_job_posting(job, profile, session)

    assert job.overall_score <= 70


@pytest.mark.asyncio
async def test_short_jd_already_capped(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    overridden = {**VALID_BREAKDOWN, "low_signal_jd": True, "overall_score": 65}

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=AsyncMock(return_value=make_tool_response(overridden)),
    ):
        await score_job_posting(job, profile, session)

    assert job.overall_score == 65


@pytest.mark.asyncio
async def test_hebrew_jd_passes_through(session):
    hebrew_description = "תפקיד מהנדס תוכנה בכיר"
    job = make_job_posting(session, description=hebrew_description)
    profile = make_user_profile(session)

    mock_create = AsyncMock(return_value=make_tool_response(VALID_BREAKDOWN))

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=mock_create,
    ):
        await score_job_posting(job, profile, session)

    # Assert the Hebrew text was passed in the messages argument
    call_kwargs = mock_create.call_args.kwargs
    messages = call_kwargs["messages"]
    assert any(hebrew_description in str(m) for m in messages)

    assert job.score_status == ScoreStatus.scored


@pytest.mark.asyncio
async def test_api_error_retries_once_then_error(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    mock_create = AsyncMock(
        side_effect=anthropic.APIError("fail", request=MagicMock(), body=None)
    )

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=mock_create,
    ):
        await score_job_posting(job, profile, session)

    assert mock_create.call_count == 2
    assert job.score_status == ScoreStatus.error


@pytest.mark.asyncio
async def test_api_error_retries_once_succeeds(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    mock_create = AsyncMock(
        side_effect=[
            anthropic.APIError("fail", request=MagicMock(), body=None),
            make_tool_response(VALID_BREAKDOWN),
        ]
    )

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=mock_create,
    ):
        await score_job_posting(job, profile, session)

    assert mock_create.call_count == 2
    assert job.score_status == ScoreStatus.scored


@pytest.mark.asyncio
async def test_malformed_json_response(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    # Missing required 'summary' field
    malformed = {k: v for k, v in VALID_BREAKDOWN.items() if k != "summary"}

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=AsyncMock(return_value=make_tool_response(malformed)),
    ):
        await score_job_posting(job, profile, session)

    assert job.score_status == ScoreStatus.error


@pytest.mark.asyncio
async def test_flags_never_null(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    overridden = {**VALID_BREAKDOWN, "flags": []}

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=AsyncMock(return_value=make_tool_response(overridden)),
    ):
        await score_job_posting(job, profile, session)

    assert job.score_status == ScoreStatus.scored
    assert json.loads(job.score_breakdown)["flags"] == []


@pytest.mark.asyncio
async def test_does_not_touch_radar_fields(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    original_url = job.url
    original_url_hash = job.url_hash
    original_title = job.title
    original_description = job.description
    original_language = job.language

    with patch(
        "backend.app.services.matcher.anthropic_client.messages.create",
        new=AsyncMock(return_value=make_tool_response(VALID_BREAKDOWN)),
    ):
        await score_job_posting(job, profile, session)

    assert job.url == original_url
    assert job.url_hash == original_url_hash
    assert job.title == original_title
    assert job.description == original_description
    assert job.language == original_language
