import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine, Session, SQLModel
from fastapi.testclient import TestClient

from backend.app.db import get_session, create_db_and_tables
from backend.app.main import app


@pytest.fixture(name="engine")
def engine_fixture():
    # StaticPool reuses the same connection so all operations share
    # the same in-memory database — required for SQLite :memory: testing.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_db_and_tables(engine)
    yield engine
    engine.dispose()


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
