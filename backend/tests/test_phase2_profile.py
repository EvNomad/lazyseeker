"""
Matcher Phase 2 — UserProfile endpoint tests.

Covers GET /profile and PUT /profile: 404 on empty DB, create on first
call, update on second call, partial update, and GET round-trip.

All tests fail with ModuleNotFoundError until the implementation is added.
"""
import uuid
from sqlmodel import Session, select

from backend.app.models.user_profile import UserProfile


def test_get_profile_404_when_empty(client):
    """GET /profile on a fresh DB must return 404."""
    response = client.get("/profile")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_put_profile_creates_on_first_call(client, session):
    """
    First PUT /profile must create a profile and return 200 with:
    - the submitted cv_markdown and preferences
    - a UUID id
    - an updated_at timestamp
    """
    response = client.put(
        "/profile",
        json={"cv_markdown": "# My CV", "preferences": "I want remote"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["cv_markdown"] == "# My CV"
    assert data["preferences"] == "I want remote"
    assert "id" in data
    # id must be a valid UUID
    uuid.UUID(data["id"])
    assert data["updated_at"] is not None


def test_put_profile_updates_existing(client, session):
    """
    Calling PUT /profile twice must result in exactly one DB row,
    with the second call's values taking precedence.
    """
    client.put("/profile", json={"cv_markdown": "# First", "preferences": "First prefs"})
    client.put("/profile", json={"cv_markdown": "# Second", "preferences": "Second prefs"})

    all_profiles = session.exec(select(UserProfile)).all()
    assert len(all_profiles) == 1
    assert all_profiles[0].cv_markdown == "# Second"
    assert all_profiles[0].preferences == "Second prefs"


def test_put_profile_partial_update(client, session):
    """
    PUT /profile with only cv_markdown must not overwrite preferences,
    and vice versa.
    """
    # Create full profile
    client.put(
        "/profile",
        json={"cv_markdown": "# Original CV", "preferences": "Original prefs"},
    )

    # Update only cv_markdown
    response = client.put("/profile", json={"cv_markdown": "# Updated CV"})
    assert response.status_code == 200

    data = response.json()
    assert data["cv_markdown"] == "# Updated CV"
    assert data["preferences"] == "Original prefs"


def test_get_profile_returns_existing(client):
    """
    After PUT /profile, GET /profile must return the same values.
    """
    client.put(
        "/profile",
        json={"cv_markdown": "# Round-trip CV", "preferences": "Round-trip prefs"},
    )

    response = client.get("/profile")
    assert response.status_code == 200

    data = response.json()
    assert data["cv_markdown"] == "# Round-trip CV"
    assert data["preferences"] == "Round-trip prefs"
