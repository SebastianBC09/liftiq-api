"""Smoke test for the health check endpoint."""

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    """The /health endpoint should respond with a 200 and status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
