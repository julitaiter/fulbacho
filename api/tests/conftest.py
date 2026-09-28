import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://fulbacho:fulbacho@localhost:5432/fulbacho_test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app import models as _models  # noqa: F401
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.base import Base

TEST_URL = settings.test_database_url or settings.database_url
if not (make_url(TEST_URL).database or "").endswith("_test"):
    raise RuntimeError("Los tests requieren una base cuyo nombre termine en '_test'.")
engine = create_engine(TEST_URL)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
