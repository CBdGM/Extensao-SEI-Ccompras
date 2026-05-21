import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin_test@ifpe.edu.br",
        "password": "Admin@123456",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "admin_test@ifpe.edu.br",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "email": "noone@ifpe.edu.br",
        "password": "Admin@123456",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, admin_token: str):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin_test@ifpe.edu.br"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, admin_user):
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "admin_test@ifpe.edu.br",
        "password": "Admin@123456",
    })
    refresh_token = login_resp.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_process_number_validation(client: AsyncClient, user_token: str):
    response = await client.post(
        "/api/v1/sei-processes/query",
        json={"numero_processo": "INVALID"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_only_endpoint(client: AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_access(client: AsyncClient, admin_token: str):
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
