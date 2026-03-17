"""Tests for the Suggestions router (Phase 6)."""
import uuid
from unittest.mock import patch, AsyncMock

import pytest
from sqlmodel import select

from backend.app.models.job_posting import JobPosting
from backend.app.models.suggestion import Suggestion, SuggestionStatus
from backend.app.services.tailor import cv_version_for_profile
from backend.tests.fixtures.seed import make_job_posting, make_user_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_suggestion(
    session,
    *,
    job: JobPosting,
    section: str = "Summary",
    original: str = "Built things at various companies.",
    suggested: str = "Led backend platform engineering at scale.",
    rationale: str = "Mirrors JD language around platform engineering.",
    status: SuggestionStatus = SuggestionStatus.pending,
    cv_version: str = "abc123",
) -> Suggestion:
    s = Suggestion(
        id=uuid.uuid4(),
        job_id=job.id,
        section=section,
        original=original,
        suggested=suggested,
        rationale=rationale,
        status=status,
        cv_version=cv_version,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/suggestions
# ---------------------------------------------------------------------------

def test_get_suggestions_empty(client, session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    response = client.get(f"/jobs/{job.id}/suggestions")
    assert response.status_code == 200

    data = response.json()
    assert data["suggestions"] == []
    expected_cv_version = cv_version_for_profile(profile)
    assert data["cv_version_current"] == expected_cv_version


def test_get_suggestions_with_items(client, session):
    job = make_job_posting(session)
    profile = make_user_profile(session)

    make_suggestion(session, job=job, section="Summary", original="orig1", suggested="sug1")
    make_suggestion(session, job=job, section="Experience", original="orig2", suggested="sug2")

    response = client.get(f"/jobs/{job.id}/suggestions")
    assert response.status_code == 200

    data = response.json()
    assert len(data["suggestions"]) == 2
    expected_cv_version = cv_version_for_profile(profile)
    assert data["cv_version_current"] == expected_cv_version


def test_get_suggestions_404_unknown_job(client):
    response = client.get(f"/jobs/{uuid.uuid4()}/suggestions")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /suggestions/{suggestion_id}
# ---------------------------------------------------------------------------

def test_patch_suggestion_approve(client, session):
    job = make_job_posting(session)
    suggestion = make_suggestion(session, job=job)

    response = client.patch(
        f"/suggestions/{suggestion.id}", json={"status": "approved"}
    )
    assert response.status_code == 200

    session.refresh(suggestion)
    assert suggestion.status == SuggestionStatus.approved


def test_patch_suggestion_reject(client, session):
    job = make_job_posting(session)
    suggestion = make_suggestion(session, job=job)

    response = client.patch(
        f"/suggestions/{suggestion.id}", json={"status": "rejected"}
    )
    assert response.status_code == 200

    session.refresh(suggestion)
    assert suggestion.status == SuggestionStatus.rejected


def test_patch_suggestion_invalid_status(client, session):
    job = make_job_posting(session)
    suggestion = make_suggestion(session, job=job)

    response = client.patch(
        f"/suggestions/{suggestion.id}", json={"status": "pending"}
    )
    assert response.status_code == 422


def test_patch_suggestion_revert_blocked(client, session):
    """Approved → rejected transition must be blocked (no reversion allowed)."""
    job = make_job_posting(session)
    suggestion = make_suggestion(session, job=job, status=SuggestionStatus.approved)

    response = client.patch(
        f"/suggestions/{suggestion.id}", json={"status": "rejected"}
    )
    assert response.status_code == 422


def test_patch_suggestion_404(client):
    response = client.patch(
        f"/suggestions/{uuid.uuid4()}", json={"status": "approved"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/tailor
# ---------------------------------------------------------------------------

def test_post_tailor_returns_generating(client, session):
    job = make_job_posting(session)
    make_user_profile(session)

    with patch(
        "backend.app.routers.suggestions.generate_suggestions",
        new_callable=AsyncMock,
    ):
        response = client.post(f"/jobs/{job.id}/tailor")

    assert response.status_code == 200
    assert response.json() == {"status": "generating"}


def test_post_tailor_404_unknown_job(client, session):
    make_user_profile(session)

    response = client.post(f"/jobs/{uuid.uuid4()}/tailor")
    assert response.status_code == 404


def test_post_tailor_404_no_profile(client, session):
    job = make_job_posting(session)
    # No profile seeded

    response = client.post(f"/jobs/{job.id}/tailor")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/tailored-cv
# ---------------------------------------------------------------------------

def test_get_tailored_cv_no_approved_returns_400(client, session):
    job = make_job_posting(session)
    make_user_profile(session)
    # Seed a pending suggestion — not approved
    make_suggestion(session, job=job)

    response = client.get(f"/jobs/{job.id}/tailored-cv")
    assert response.status_code == 400


def test_get_tailored_cv_returns_markdown(client, session):
    cv_text = "# My CV\n\n## Experience\n\nBuilt things at various companies."
    job = make_job_posting(session)
    profile = make_user_profile(session, cv_markdown=cv_text)

    make_suggestion(
        session,
        job=job,
        original="Built things at various companies.",
        suggested="Led backend platform engineering.",
        status=SuggestionStatus.approved,
        cv_version=cv_version_for_profile(profile),
    )

    response = client.get(f"/jobs/{job.id}/tailored-cv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Led backend platform engineering." in response.text


def test_get_tailored_cv_404_unknown_job(client, session):
    make_user_profile(session)

    response = client.get(f"/jobs/{uuid.uuid4()}/tailored-cv")
    assert response.status_code == 404


def test_get_tailored_cv_404_no_profile(client, session):
    job = make_job_posting(session)
    # No profile seeded

    response = client.get(f"/jobs/{job.id}/tailored-cv")
    assert response.status_code == 404
