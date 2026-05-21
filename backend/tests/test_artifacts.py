import pytest
import io
from httpx import AsyncClient
from app.core.file_validator import calculate_hashes, validate_extension, block_executable
from fastapi import HTTPException


def test_calculate_hashes():
    content = b"%PDF-1.4 test content"
    sha256, md5 = calculate_hashes(content)
    assert len(sha256) == 64
    assert len(md5) == 32


def test_validate_extension_pdf():
    ext = validate_extension("documento.pdf")
    assert ext == "pdf"


def test_validate_extension_invalid():
    with pytest.raises(HTTPException) as exc:
        validate_extension("malware.exe")
    assert exc.value.status_code == 400


def test_validate_extension_no_extension():
    with pytest.raises(HTTPException) as exc:
        validate_extension("noextension")
    assert exc.value.status_code == 400


def test_block_executable_mz_header():
    with pytest.raises(HTTPException) as exc:
        block_executable("test.pdf", b"MZ\x90\x00")
    assert exc.value.status_code == 400


def test_block_executable_elf_header():
    with pytest.raises(HTTPException) as exc:
        block_executable("test.pdf", b"\x7fELF\x00")
    assert exc.value.status_code == 400


def test_block_executable_dangerous_ext():
    with pytest.raises(HTTPException) as exc:
        block_executable("script.sh", b"#!/bin/bash")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_artifact_requires_auth(client: AsyncClient):
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake")
    response = await client.post(
        "/api/v1/artifacts/",
        files={"file": ("test.pdf", fake_pdf, "application/pdf")},
        data={
            "sei_process_id": "00000000-0000-0000-0000-000000000000",
            "tipo_artefato": "DFD",
            "identificador_compras": "TEST-001",
            "nivel_acesso": "publico",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_artifacts_empty(client: AsyncClient, user_token: str):
    response = await client.get(
        "/api/v1/artifacts/",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
