import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.modules.users.models import User

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_user_id():
    return uuid.uuid4()


async def test_get_available_repositories(mock_db, mock_user_id):
    with patch("src.modules.repositories.service._get_decrypted_token", return_value="fake_token"):
        with patch(
            "src.modules.repositories.service.fetch_user_repositories", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = [
                {
                    "id": 999,
                    "owner": {"login": "testuser"},
                    "name": "reponis",
                    "full_name": "testuser/reponis",
                    "private": False,
                    "description": "Test repo",
                    "language": "Python",
                    "html_url": "https://github.com/testuser/reponis",
                }
            ]

            # Since we mock the DB, we need to mock the get_db dependency
            from src.core.database import get_db

            app.dependency_overrides[get_db] = lambda: mock_db

            # To mock get_current_user_id, we need to override the dependency in auth
            from src.modules.auth.dependencies import get_current_user_from_cookie

            app.dependency_overrides[get_current_user_from_cookie] = lambda: User(
                id=mock_user_id, github_id=123, username="testuser", email="test@example.com"
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/repositories/available")

            assert response.status_code == 200
            data = response.json()
            assert len(data["repositories"]) == 1
            assert data["repositories"][0]["github_repo_id"] == 999
            assert data["repositories"][0]["visibility"] == "public"

            # cleanup
            app.dependency_overrides.clear()


async def test_connect_repository(mock_db, mock_user_id):
    with patch("src.modules.repositories.service._get_decrypted_token", return_value="fake_token"):
        with patch(
            "src.modules.repositories.service.fetch_repository_by_id", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = {
                "id": 999,
                "owner": {"login": "testuser"},
                "name": "reponis",
                "full_name": "testuser/reponis",
                "private": False,
                "description": "Test repo",
                "language": "Python",
                "html_url": "https://github.com/testuser/reponis",
                "default_branch": "main",
            }

            # Mock the repository methods
            with patch("src.modules.repositories.service.RepositoriesRepository") as MockRepoClass:
                mock_repo_instance = MockRepoClass.return_value
                mock_repo_instance.get_by_github_id = AsyncMock(return_value=None)
                mock_repo_instance.disconnect_active = AsyncMock()
                mock_repo_instance.create = AsyncMock()

                # Mock current user and db
                from src.core.database import get_db
                from src.modules.auth.dependencies import get_current_user_from_cookie

                async def mock_refresh(instance):
                    if getattr(instance, "id", None) is None:
                        instance.id = uuid.uuid4()
                    if getattr(instance, "connected_at", None) is None:
                        from datetime import datetime, timezone

                        instance.connected_at = datetime.now(timezone.utc)

                mock_db.refresh = AsyncMock(side_effect=mock_refresh)

                app.dependency_overrides[get_db] = lambda: mock_db
                app.dependency_overrides[get_current_user_from_cookie] = lambda: User(
                    id=mock_user_id, github_id=123, username="testuser", email="test@example.com"
                )

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/v1/repositories/connect", json={"github_repo_id": 999}
                    )

                assert response.status_code == 201
                data = response.json()
                assert data["github_repo_id"] == 999
                assert data["is_active"] is True
                assert data["sync_status"] == "never_synced"

                # cleanup
                app.dependency_overrides.clear()
