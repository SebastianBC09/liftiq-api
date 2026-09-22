"""HTTP payloads and helpers shared across auth integration tests."""

from typing import Any

from httpx import AsyncClient

REGISTER = {
    "email": "person@example.com",
    "password": "a-long-test-password",
    "firstName": "Ada",
    "lastName": "Lovelace",
    "heightCm": 170.25,
    "weightKg": 65.5,
    "experienceLevel": "beginner",
    "goal": "technique",
}
AUTH = "/api/v1/auth"
ME = "/api/v1/users/me"


async def register(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    response = await client.post(f"{AUTH}/register", json=REGISTER | overrides)
    assert response.status_code == 201, response.text
    return response.json()


def bearer(result: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {result['accessToken']}"}


async def refresh(client: AsyncClient, result: dict[str, Any]):
    return await client.post(f"{AUTH}/refresh", json={"refreshToken": result["refreshToken"]})
