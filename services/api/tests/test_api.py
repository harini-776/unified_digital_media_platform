"""Basic API endpoint tests."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_root(client):
    async with client as c:
        response = await c.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "TrustMedia API"


@pytest.mark.asyncio
async def test_health(client):
    async with client as c:
        response = await c.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_upload_no_file(client):
    async with client as c:
        response = await c.post("/api/v1/videos/upload")
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_upload_wrong_type(client):
    async with client as c:
        response = await c.post(
            "/api/v1/videos/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_job_not_found(client):
    async with client as c:
        response = await c.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_videos_list(client):
    async with client as c:
        response = await c.get("/api/v1/videos")
        assert response.status_code == 200
        data = response.json()
        assert "videos" in data
        assert "total" in data
