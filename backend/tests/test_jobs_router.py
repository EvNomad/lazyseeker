import uuid
import pytest
from unittest.mock import patch, AsyncMock
from sqlmodel import select

from backend.app.models.job_posting import JobPosting, ScoreStatus, ApplicationStatus, Language, Source
from backend.app.models.company import Company
from backend.tests.fixtures.seed import make_company, make_job_posting, make_user_profile


def test_get_jobs_empty(client):
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == []


def test_get_jobs_returns_postings(client, session):
    make_job_posting(session)
    make_job_posting(session)
    response = client.get("/jobs")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_jobs_filter_min_score(client, session):
    company = make_company(session)

    job_high = make_job_posting(session, company=company)
    job_high.overall_score = 90
    session.add(job_high)
    session.commit()

    job_low = make_job_posting(session, company=company)
    job_low.overall_score = 40
    session.add(job_low)
    session.commit()

    response = client.get("/jobs?min_score=65")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["overall_score"] == 90


def test_get_jobs_filter_language(client, session):
    company = make_company(session)
    make_job_posting(session, language="he", company=company)
    make_job_posting(session, language="en", company=company)

    response = client.get("/jobs?language=he")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["language"] == "he"


def test_get_job_by_id(client, session):
    job = make_job_posting(session)
    response = client.get(f"/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert "company" in data


def test_get_job_404(client):
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_patch_job_status_valid(client, session):
    job = make_job_posting(session)
    response = client.patch(f"/jobs/{job.id}/status", json={"application_status": "reviewing"})
    assert response.status_code == 200
    data = response.json()
    assert data["application_status"] == "reviewing"


def test_patch_job_status_invalid(client, session):
    job = make_job_posting(session)
    response = client.patch(f"/jobs/{job.id}/status", json={"application_status": "flying"})
    assert response.status_code == 422


def test_retry_score_returns_pending(client, session):
    job = make_job_posting(session, score_status="error")
    make_user_profile(session)

    with patch("backend.app.routers.jobs.score_job_posting", new_callable=AsyncMock) as mock_score:
        response = client.post(f"/jobs/{job.id}/retry-score")

    assert response.status_code == 200
    assert response.json() == {"score_status": "pending"}


def test_retry_score_409_if_already_scored(client, session):
    job = make_job_posting(session, score_status="scored")
    make_user_profile(session)

    response = client.post(f"/jobs/{job.id}/retry-score")
    assert response.status_code == 409


def test_retry_score_404_no_profile(client, session):
    job = make_job_posting(session, score_status="error")
    # No profile seeded

    response = client.post(f"/jobs/{job.id}/retry-score")
    assert response.status_code == 404
