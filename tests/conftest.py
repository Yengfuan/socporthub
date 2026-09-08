import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "development"
os.environ["TELEGRAM_BOT_TOKEN"] = ""  # keep dev initData bypass active
os.environ["ADMIN_TELEGRAM_IDS"] = "999"

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, get_db
from api.main import app
from api.models import Committee


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    session = TestSession()
    session.add_all([Committee(name="Block 2", color="#E67C73"), Committee(name="Soccom", color="#D81B60")])
    session.commit()
    session.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def auth_header(telegram_id: int) -> dict:
    return {"X-Telegram-Init-Data": f"dev_telegram_id={telegram_id}"}
