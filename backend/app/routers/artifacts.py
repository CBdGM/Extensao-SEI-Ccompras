import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import io
from app.database import get_db
from app.models.artifact import ImportedArtifact, ArtifactType, AccessLevel, ArtifactStatus
from app.models.user import User
from app.core.deps import get_current_user, get_client_ip
from app.schemas.artifact import ArtifactCreate, ArtifactResponse, ArtifactDeleteResponse, ArtifactSendToSEIRequest
from app.services.artifact_service import save_artifact, soft_delete_artifact, get_artifact_file
from app.services.sei_send_service import send_artifact_to_sei
from app.services.audit_service import log_action
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/artifacts", tags=["Artefatos"])


@router.post("/", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    request: Request,
    file: UploadFile = File(...),
    sei_process_id: UUID = Form(...),
    tipo_artefato: ArtifactType = Form(...),
    identificador_compras: str = Form(...),
    nivel_acesso: AccessLevel = Form(...),
    observacao: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        "UPLOAD ARTEFATO  user=%s  tipo=%s  arquivo=%s  processo=%s",
        current_user.email, tipo_artefato.value, file.filename, sei_process_id,
    )
    data = ArtifactCreate(
        sei_process_id=sei_process_id,
        tipo_artefato=tipo_artefato,
        identificador_compras=identificador_compras,
        nivel_acesso=nivel_acesso,
        observacao=observacao,
    )

    artifact = await save_artifact(db, current_user, data, file)
    logger.info(
        "UPLOAD OK  artifact_id=%s  sha256=%s  size=%d bytes  path=%s",
        artifact.id, artifact.sha256_hash, artifact.file_size, artifact.storage_path,
    )

    await log_action(
        db,
        action="ARTIFACT_UPLOADED",
        user_id=current_user.id,
        entity_type="artifact",
        entity_id=str(artifact.id),
        ip_address=get_client_ip(request),
        metadata={
            "tipo_artefato": artifact.tipo_artefato.value,
            "identificador_compras": artifact.identificador_compras,
            "sha256": artifact.sha256_hash,
            "file_size": artifact.file_size,
            "sei_process_id": str(sei_process_id),
        },
    )
    return artifact


@router.get("/", response_model=list[ArtifactResponse])
async def list_artifacts(
    sei_process_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    query = select(ImportedArtifact).where(ImportedArtifact.status == ArtifactStatus.ACTIVE)
    if sei_process_id:
        query = query.where(ImportedArtifact.sei_process_id == sei_process_id)
    query = query.order_by(ImportedArtifact.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.id == artifact_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefato não encontrado")
    return artifact


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact, content = await get_artifact_file(db, artifact_id, current_user)

    await log_action(
        db,
        action="ARTIFACT_DOWNLOADED",
        user_id=current_user.id,
        entity_type="artifact",
        entity_id=str(artifact_id),
        ip_address=get_client_ip(request),
    )

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.original_filename}"',
            "X-Content-SHA256": artifact.sha256_hash,
        },
    )


@router.delete("/{artifact_id}", response_model=ArtifactDeleteResponse)
async def delete_artifact(
    artifact_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact = await soft_delete_artifact(db, artifact_id, current_user)

    await log_action(
        db,
        action="ARTIFACT_DELETED",
        user_id=current_user.id,
        entity_type="artifact",
        entity_id=str(artifact_id),
        ip_address=get_client_ip(request),
        metadata={"sha256": artifact.sha256_hash, "original_filename": artifact.original_filename},
    )

    return ArtifactDeleteResponse(
        message="Artefato removido com sucesso (exclusão lógica). Trilha de auditoria mantida.",
        artifact_id=artifact_id,
        deleted_at=artifact.deleted_at or datetime.utcnow(),
    )


@router.post("/{artifact_id}/send-to-sei", response_model=ArtifactResponse)
async def send_artifact_to_sei_endpoint(
    artifact_id: UUID,
    body: ArtifactSendToSEIRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload the artifact file to SEI (adicionarArquivo) and include it
    as an external document in the process (incluirDocumento Tipo=R).

    Requires SEI_ENABLE_WRITE_OPERATIONS=true or enable_write_operations=true in config.
    Idempotent: returns 409 if artifact was already successfully sent.
    """
    logger.info(
        "SEND-TO-SEI ARTEFATO  artifact_id=%s  user=%s  id_serie_override=%s",
        artifact_id, current_user.email, body.id_serie_override,
    )
    artifact = await send_artifact_to_sei(
        db, artifact_id, current_user, id_serie_override=body.id_serie_override
    )
    logger.info(
        "SEND-TO-SEI OK  artifact_id=%s  doc_sei=%s  doc_number=%s",
        artifact_id, artifact.sei_document_id, artifact.sei_document_number,
    )
    await log_action(
        db,
        action="ARTIFACT_SENT_TO_SEI",
        user_id=current_user.id,
        entity_type="artifact",
        entity_id=str(artifact_id),
        ip_address=get_client_ip(request),
        metadata={
            "sei_document_id": artifact.sei_document_id,
            "sei_document_number": artifact.sei_document_number,
        },
    )
    return artifact
