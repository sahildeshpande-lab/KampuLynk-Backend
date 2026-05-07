import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

test_db_path = Path(tempfile.gettempdir()) / f"test_db_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"

from app.main import app, Base, engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except PermissionError:
            pass 

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers():
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}
    return _headers
