import os
import sys
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["LLM_PROVIDER"] = "mock"

from app.core.config import settings
settings.LLM_PROVIDER = "mock"

from app.db.base import Base
from app.db.session import create_all, get_db
from app.services.ingestion.seed_loader import load_seed_data
import app.models  # noqa: F401
from app.main import app as fastapi_app


@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite engine for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_all(target_engine=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def seeded_engine():
    """Create an in-memory SQLite engine and load seed data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    load_seed_data(target_engine=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def seeded_session(seeded_engine) -> Generator[Session, None, None]:
    """Provide a database session connected to the seeded database."""
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=seeded_engine,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(seeded_engine) -> Generator[TestClient, None, None]:
    """Provide FastAPI test client wired to the seeded database."""
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=seeded_engine,
    )

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
