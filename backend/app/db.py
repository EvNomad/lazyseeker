from sqlmodel import create_engine, SQLModel, Session
from typing import Generator
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lazyseeker.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables(eng=None) -> None:
    """Create all tables. Accepts an optional engine for testing with in-memory DBs."""
    target = eng if eng is not None else engine
    SQLModel.metadata.create_all(target)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
