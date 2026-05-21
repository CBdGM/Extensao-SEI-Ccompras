import uuid
import os
import aiofiles
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile, HTTPException, status

from app.config import settings
from app.models.artifact import ImportedArtifact, ArtifactStatus
from app.models.document import ImportDocument
from app.models.sei_process import SEIProcess
from app.models.user import User
from app.core.file_validator import (
    validate_extension,
    validate_magic_bytes,
    validate_mime_type,
    validate_file_size,
    block_executable,
    calculate_hashes,
    safe_filename,
)
from app.schemas.artifact import ArtifactCreate

logger = logging.getLogger(__name__)


async def _try_rebuild(db: AsyncSession, sei_process_id: uuid.UUID) -> None:
    """Silently rebuild the import document for this process if one exists."""
    try:
        from app.services.document_service import rebuild_import_document_content
        result = await db.execute(
            select(ImportDocument).where(ImportDocument.sei_process_id == sei_process_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            await rebuild_import_document_content(db, doc)
    except Exception as exc:
        logger.warning("Rebuild after artifact change failed (non-fatal): %s", exc)


async def save_artifact(
    db: AsyncSession,
    current_user: User,
    data: ArtifactCreate,
    file: UploadFile,
) -> ImportedArtifact:
    result = await db.execute(
        select(SEIProcess).where(SEIProcess.id == data.sei_process_id)
    )
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo SEI não encontrado",
        )

    content = await file.read()
    validate_file_size(len(content), settings.max_file_size_bytes)

    original_name = safe_filename(file.filename or "arquivo.pdf")
    ext = validate_extension(original_name)
    block_executable(original_name, content)
    validate_magic_bytes(content, ext)
    validate_mime_type(file.content_type or "")
    sha256, md5 = calculate_hashes(content)

    process_dir = os.path.join(settings.UPLOAD_DIR, str(data.sei_process_id))
    os.makedirs(process_dir, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    storage_path = os.path.join(process_dir, stored_name)

    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(content)

    artifact = ImportedArtifact(
        sei_process_id=data.sei_process_id,
        user_id=current_user.id,
        tipo_artefato=data.tipo_artefato,
        identificador_compras=data.identificador_compras,
        nivel_acesso=data.nivel_acesso,
        original_filename=original_name,
        stored_filename=stored_name,
        mime_type=file.content_type or "application/pdf",
        file_size=len(content),
        sha256_hash=sha256,
        md5_hash=md5,
        storage_path=storage_path,
        observacao=data.observacao,
        status=ArtifactStatus.ACTIVE,
    )
    db.add(artifact)
    await db.flush()
    await db.refresh(artifact)

    # Rebuild the import document to include the new artifact
    await _try_rebuild(db, data.sei_process_id)

    return artifact


async def soft_delete_artifact(
    db: AsyncSession,
    artifact_id: uuid.UUID,
    current_user: User,
) -> ImportedArtifact:
    result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.id == artifact_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefato não encontrado")

    sei_process_id = artifact.sei_process_id
    artifact.status = ArtifactStatus.DELETED
    artifact.deleted_at = datetime.utcnow()
    artifact.deleted_by = current_user.id
    await db.flush()

    # Rebuild comprovante reflecting the deletion
    await _try_rebuild(db, sei_process_id)

    return artifact


async def get_artifact_file(
    db: AsyncSession,
    artifact_id: uuid.UUID,
    current_user: User,
) -> tuple[ImportedArtifact, bytes]:
    result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.id == artifact_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefato não encontrado")

    if not os.path.exists(artifact.storage_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado no storage")

    async with aiofiles.open(artifact.storage_path, "rb") as f:
        content = await f.read()

    return artifact, content
