from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app import auth, models  # noqa: F401  # models registers every table with Base.metadata
from app.db import Base, create_sqlite_engine, get_db
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    """TestClient against a throwaway SQLite file, never the dev database
    in modules/wg/data/ (CLAUDE.md: tests use in-memory/tmp SQLite).

    Patches both the `get_db` dependency (used by route handlers) and
    app.auth.SessionLocal (used directly by the access_gate middleware,
    which runs outside FastAPI's DI) so both sides see the same data.
    """
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(engine, expire_on_commit=False)

    def override_get_db() -> Generator[Session]:
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(auth, "SessionLocal", testing_session_local)
    test_client = TestClient(app)
    test_client.session_local = testing_session_local  # lets tests seed data directly
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def session_local(tmp_path: Path) -> sessionmaker:
    """A sessionmaker bound to a throwaway SQLite file with every table
    already created - for tests that drive app.cli directly rather than
    through the FastAPI app (so the `client` override doesn't apply)."""
    engine = create_sqlite_engine(f"sqlite:///{tmp_path / 'cli-test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
