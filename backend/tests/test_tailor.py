import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
from sqlmodel import select

from backend.app.models.suggestion import Suggestion, SuggestionStatus
from backend.app.services.tailor import (
    TailorError,
    assemble_tailored_cv,
    cv_version_for_profile,
    generate_suggestions,
)
from backend.tests.fixtures.seed import make_job_posting, make_user_profile


def make_tool_response(suggestions_list: list[dict]):
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.input = {"suggestions": suggestions_list}
    msg = MagicMock()
    msg.content = [tool_use]
    return msg


VALID_SUGGESTIONS = [
    {"section": "Experience", "original": "Built systems", "suggested": "Built scalable systems", "rationale": "JD mentions scalability"},
    {"section": "Skills", "original": "Python", "suggested": "Python (FastAPI, SQLModel)", "rationale": "JD requires FastAPI"},
    {"section": "Summary", "original": "Engineer", "suggested": "Senior Backend Engineer", "rationale": "JD is senior level"},
]


@pytest.mark.asyncio
async def test_happy_path_suggestions(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    with patch("backend.app.services.tailor.anthropic_client.messages.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_tool_response(VALID_SUGGESTIONS)
        result = await generate_suggestions(job, profile, session)

    assert len(result) == 3
    all_suggestions = session.exec(select(Suggestion).where(Suggestion.job_id == job.id)).all()
    assert len(all_suggestions) == 3
    for s in all_suggestions:
        assert s.status == SuggestionStatus.pending
        assert len(s.cv_version) == 64
        assert all(c in "0123456789abcdef" for c in s.cv_version)


@pytest.mark.asyncio
async def test_max_6_enforced(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    eight_suggestions = [
        {"section": f"Sec{i}", "original": f"orig{i}", "suggested": f"sugg{i}", "rationale": f"reason{i}"}
        for i in range(8)
    ]

    with patch("backend.app.services.tailor.anthropic_client.messages.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_tool_response(eight_suggestions)
        result = await generate_suggestions(job, profile, session)

    assert len(result) == 6
    all_suggestions = session.exec(select(Suggestion).where(Suggestion.job_id == job.id)).all()
    assert len(all_suggestions) == 6


@pytest.mark.asyncio
async def test_cv_version_is_sha256_of_markdown(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    expected_cv_version = hashlib.sha256(profile.cv_markdown.encode()).hexdigest()

    with patch("backend.app.services.tailor.anthropic_client.messages.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_tool_response(VALID_SUGGESTIONS)
        suggestions = await generate_suggestions(job, profile, session)

    assert suggestions[0].cv_version == expected_cv_version


@pytest.mark.asyncio
async def test_hebrew_jd_passes_through(session):
    hebrew_description = "אנו מחפשים מהנדס תוכנה מנוסה לצוות הפלטפורמה שלנו. נדרש ניסיון ב-Python ו-FastAPI."
    job = make_job_posting(session, description=hebrew_description)
    profile = make_user_profile(session)

    with patch("backend.app.services.tailor.anthropic_client.messages.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_tool_response(VALID_SUGGESTIONS)
        await generate_suggestions(job, profile, session)

    call_kwargs = mock_create.call_args
    messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else None
    if messages_arg is None:
        # Try positional args
        all_kwargs = call_kwargs[1] if len(call_kwargs) > 1 else {}
        messages_arg = all_kwargs.get("messages", [])

    # Find the messages in the call
    kwargs = mock_create.call_args.kwargs
    messages = kwargs.get("messages", [])
    user_message_content = messages[0]["content"]
    assert hebrew_description in user_message_content


@pytest.mark.asyncio
async def test_api_error_raises_tailor_error(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    with patch("backend.app.services.tailor.anthropic_client.messages.create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = anthropic.APIError("fail", request=MagicMock(), body=None)
        with pytest.raises(TailorError):
            await generate_suggestions(job, profile, session)


@pytest.mark.asyncio
async def test_malformed_response_raises(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    malformed = [{"section": "x"}]  # missing required fields

    with patch("backend.app.services.tailor.anthropic_client.messages.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_tool_response(malformed)
        with pytest.raises(TailorError):
            await generate_suggestions(job, profile, session)


@pytest.mark.asyncio
async def test_regenerate_replaces_pending_keeps_approved(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    # Seed 2 pending + 1 approved
    for i in range(2):
        s = Suggestion(job_id=job.id, section="X", original=f"orig{i}", suggested=f"sugg{i}",
                       rationale="r", cv_version="old", status=SuggestionStatus.pending)
        session.add(s)
    approved = Suggestion(job_id=job.id, section="Y", original="keep", suggested="keep this",
                          rationale="r", cv_version="old", status=SuggestionStatus.approved)
    session.add(approved)
    session.commit()

    with patch("backend.app.services.tailor.anthropic_client.messages.create",
               new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_tool_response(VALID_SUGGESTIONS)
        result = await generate_suggestions(job, profile, session)

    all_suggestions = session.exec(select(Suggestion).where(Suggestion.job_id == job.id)).all()
    pending = [s for s in all_suggestions if s.status == SuggestionStatus.pending]
    approved_remaining = [s for s in all_suggestions if s.status == SuggestionStatus.approved]
    assert len(approved_remaining) == 1
    assert approved_remaining[0].id == approved.id
    assert len(pending) == 3  # new ones from VALID_SUGGESTIONS


@pytest.mark.asyncio
async def test_cv_version_mismatch_detection(session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    # Seed a suggestion with old hash
    old_suggestion = Suggestion(
        job_id=job.id, section="X", original="orig", suggested="sugg",
        rationale="r", cv_version="old_hash", status=SuggestionStatus.pending
    )
    session.add(old_suggestion)
    session.commit()

    # Update profile's cv_markdown
    profile.cv_markdown = "# Updated CV\n\nNew content here."
    session.add(profile)
    session.commit()
    session.refresh(profile)

    new_cv_version = cv_version_for_profile(profile)
    assert new_cv_version != "old_hash"


def test_assemble_tailored_cv_replaces_text(session):
    cv = "I built systems."
    suggestion = Suggestion(
        job_id=None,  # not persisted, just for testing
        section="Experience",
        original="built systems",
        suggested="built scalable systems",
        rationale="JD mentions scalability",
        cv_version="abc",
        status=SuggestionStatus.pending,
    )
    result = assemble_tailored_cv(cv, [suggestion])
    assert "built scalable systems" in result


def test_assemble_tailored_cv_unmatched_section(session):
    cv = "I wrote code."
    suggestion = Suggestion(
        job_id=None,
        section="Experience",
        original="text not in cv",
        suggested="new text",
        rationale="some reason",
        cv_version="abc",
        status=SuggestionStatus.pending,
    )
    result = assemble_tailored_cv(cv, [suggestion])
    assert "## Unmatched Suggestions" in result
