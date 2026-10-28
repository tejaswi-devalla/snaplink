from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client() -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url=None,
        public_base_url="https://snap.test",
        admin_api_key="test-admin-secret-key-with-at-least-32-chars",
        auto_create_tables=True,
        create_limit=25,
        create_window_seconds=3600,
        stats_limit=25,
        stats_window_seconds=60,
        redirect_limit=100,
        redirect_window_seconds=60,
        report_limit=10,
        report_window_seconds=3600,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
