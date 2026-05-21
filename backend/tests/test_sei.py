import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_query_process_invalid_format(client: AsyncClient, user_token: str):
    response = await client.post(
        "/api/v1/sei-processes/query",
        json={"numero_processo": "123"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_process_valid_format_no_sei_config(client: AsyncClient, user_token: str):
    response = await client.post(
        "/api/v1/sei-processes/query",
        json={"numero_processo": "23298.000001/2024-01"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    # Should fail gracefully when SEI is not configured
    assert response.status_code in (502, 201)


@pytest.mark.asyncio
async def test_list_processes_empty(client: AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/sei-processes/",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_process_not_found(client: AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/sei-processes/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sei_config_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/sei-config/",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sei_config_create(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/api/v1/sei-config/",
        json={
            "soap_url": "https://sei-testes.ifpe.edu.br/sei/ws/SeiWS.php",
            "sigla_sistema": "MVP",
            "identificacao_servico": "CHAVE_TESTE_123",
            "id_unidade_default": "110001189",
            "sin_retornar_assuntos": True,
            "sin_retornar_interessados": True,
            "sin_retornar_observacoes": True,
            "sin_retornar_ultimo_andamento": True,
            "sin_retornar_unidades": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["soap_url"] == "https://sei-testes.ifpe.edu.br/sei/ws/SeiWS.php"
    # Credential must NOT be returned
    assert "identificacao_servico" not in data
    assert "identificacao_servico_encrypted" not in data


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
