"""
Orchestrates sending artifacts and comprovation documents to SEI.

Handles idempotency guards, intermediate-state persistence,
SEIWriteOperation audit records, and artifact locking.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.config import settings
from app.models.artifact import ImportedArtifact, ArtifactStatus, SendToSEIStatus
from app.models.document import ImportDocument, DocumentStatus
from app.models.document import SendToSEIStatus as DocSendStatus
from app.models.sei_process import SEIProcess
from app.models.sei_write_operation import SEIWriteOperation
from app.models.user import User
from app.services.sei_service import SEIService

logger = logging.getLogger(__name__)


async def _record_write_op(
    db: AsyncSession,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: str,
    operation: str,
    status_val: str,
    request_summary: Optional[dict] = None,
    response_summary: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> None:
    op = SEIWriteOperation(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        status=status_val,
        request_summary_json=json.dumps(request_summary) if request_summary else None,
        response_summary_json=json.dumps(response_summary) if response_summary else None,
        error_message=error_message[:2000] if error_message else None,
    )
    db.add(op)
    await db.flush()


async def send_artifact_to_sei(
    db: AsyncSession,
    artifact_id: uuid.UUID,
    current_user: User,
    id_serie_override: Optional[str] = None,
) -> ImportedArtifact:
    """
    Full send-to-SEI flow for an artifact:
      1. Idempotency guard
      2. adicionarArquivo
      3. incluirDocumento (Tipo=R)
      4. Update artifact record
    """
    # ── Fetch artifact ────────────────────────────────────────────────────────
    result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.id == artifact_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefato não encontrado")

    # ── Idempotency guard ─────────────────────────────────────────────────────
    if artifact.send_to_sei_status == SendToSEIStatus.SENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Este artefato já foi enviado ao SEI "
                f"(documento {artifact.sei_document_number or artifact.sei_document_id}). "
                "Para reenviar, contate um administrador."
            ),
        )

    # Allow retry only if previous attempt failed at document step
    # (sei_file_id already saved = arquivo was uploaded, only documento failed)
    retry_doc_only = (
        artifact.send_to_sei_status == SendToSEIStatus.FILE_UPLOADED_DOCUMENT_FAILED
        and artifact.sei_file_id
    )

    # ── Feature flag ──────────────────────────────────────────────────────────
    sei_service = SEIService(db)
    config = await sei_service._get_config()
    if not sei_service._write_enabled(config):
        logger.warning("BLOQUEADO write ops desabilitadas  artifact_id=%s", artifact_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operações de escrita no SEI estão desabilitadas. Habilite SEI_ENABLE_WRITE_OPERATIONS.",
        )

    # ── Fetch process ─────────────────────────────────────────────────────────
    proc_result = await db.execute(
        select(SEIProcess).where(SEIProcess.id == artifact.sei_process_id)
    )
    process = proc_result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo SEI não encontrado")

    logger.info(
        "ARTEFATO→SEI INICIADO  artifact_id=%s  arquivo=%s  processo=%s  retry_doc_only=%s",
        artifact_id, artifact.original_filename, process.numero_processo, retry_doc_only,
    )

    # ── Mark as pending ───────────────────────────────────────────────────────
    artifact.send_to_sei_status = SendToSEIStatus.PENDING
    artifact.send_to_sei_error = None
    await db.flush()

    id_arquivo = artifact.sei_file_id  # may already exist on retry

    # ── Step 1: adicionarArquivo (skip if retrying doc only) ─────────────────
    if not retry_doc_only:
        logger.info(
            "SOAP adicionarArquivo  arquivo=%s  size=%d  path=%s",
            artifact.original_filename, artifact.file_size, artifact.storage_path,
        )
        req_summary = {
            "operation": "adicionarArquivo",
            "file": artifact.original_filename,
            "size": artifact.file_size,
            "processo": process.numero_processo,
        }
        try:
            id_arquivo = await sei_service.adicionar_arquivo(
                file_path=artifact.storage_path,
                original_filename=artifact.original_filename,
                md5_hash=artifact.md5_hash,
                file_size=artifact.file_size,
            )
            logger.info("SOAP adicionarArquivo OK  id_arquivo=%s", id_arquivo)
            artifact.sei_file_id = id_arquivo
            await db.flush()
            await _record_write_op(
                db, current_user.id, "artifact", str(artifact_id),
                "adicionarArquivo", "success",
                request_summary=req_summary,
                response_summary={"id_arquivo": id_arquivo},
            )
        except Exception as e:
            err = str(e)[:500]
            logger.error("SOAP adicionarArquivo FALHOU  artifact_id=%s  erro=%s", artifact_id, err)
            artifact.send_to_sei_status = SendToSEIStatus.ERROR
            artifact.send_to_sei_error = err
            await db.flush()
            await _record_write_op(
                db, current_user.id, "artifact", str(artifact_id),
                "adicionarArquivo", "error",
                request_summary=req_summary, error_message=err,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Falha ao enviar arquivo ao SEI: {err}")

    # ── Step 2: incluirDocumento (Tipo=R) ─────────────────────────────────────
    # Use the process's own autuacao date (already accepted by SEI) to avoid
    # "Data do protocolo não pode estar no futuro" on servers with stale clocks.
    data_doc = process.data_autuacao or (artifact.created_at or datetime.utcnow()).strftime("%d/%m/%Y")
    logger.info(
        "SOAP incluirDocumento  processo=%s  id_arquivo=%s  tipo=%s  id_serie_override=%s",
        process.numero_processo, id_arquivo, artifact.tipo_artefato.value, id_serie_override,
    )
    req_summary = {
        "operation": "incluirDocumento",
        "processo": process.numero_processo,
        "identificador": artifact.identificador_compras,
        "tipo_artefato": artifact.tipo_artefato.value,
    }
    try:
        result_doc = await sei_service.incluir_documento_externo(
            numero_processo=process.numero_processo,
            id_arquivo=id_arquivo,
            original_filename=artifact.original_filename,
            tipo_artefato=artifact.tipo_artefato.value,
            identificador_compras=artifact.identificador_compras,
            nivel_acesso=artifact.nivel_acesso.value,
            data=data_doc,
            id_serie_override=id_serie_override,
        )
        logger.info("SOAP incluirDocumento OK  resultado=%s", result_doc)
    except Exception as e:
        err = str(e)[:500]
        logger.error("SOAP incluirDocumento FALHOU  artifact_id=%s  erro=%s", artifact_id, err)
        # Keep sei_file_id so a retry can skip adicionarArquivo
        artifact.send_to_sei_status = SendToSEIStatus.FILE_UPLOADED_DOCUMENT_FAILED
        artifact.send_to_sei_error = err
        await db.flush()
        await _record_write_op(
            db, current_user.id, "artifact", str(artifact_id),
            "incluirDocumento", "error",
            request_summary=req_summary, error_message=err,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Arquivo enviado mas falha ao incluir documento no SEI: {err}",
        )

    # ── Persist success ───────────────────────────────────────────────────────
    artifact.sei_document_id = result_doc.get("id_documento")
    artifact.sei_document_number = result_doc.get("documento_formatado")
    artifact.sei_document_link = result_doc.get("link_acesso")
    artifact.sent_to_sei_at = datetime.utcnow()
    artifact.send_to_sei_status = SendToSEIStatus.SENT
    artifact.send_to_sei_error = None
    artifact.document_locked = True
    await db.flush()

    await _record_write_op(
        db, current_user.id, "artifact", str(artifact_id),
        "incluirDocumento", "success",
        request_summary=req_summary,
        response_summary={
            "id_documento": result_doc.get("id_documento"),
            "documento_formatado": result_doc.get("documento_formatado"),
        },
    )

    # Rebuild consolidated comprovante to reflect new SEI document number/link
    try:
        from app.services.document_service import rebuild_import_document_content
        from sqlalchemy import select as _select
        doc_result = await db.execute(
            _select(ImportDocument).where(ImportDocument.sei_process_id == artifact.sei_process_id)
        )
        imp_doc = doc_result.scalar_one_or_none()
        if imp_doc:
            await rebuild_import_document_content(db, imp_doc)
    except Exception as exc:
        logger.warning("Rebuild after artifact SEI send failed (non-fatal): %s", exc)

    await db.refresh(artifact)
    return artifact


async def send_document_to_sei(
    db: AsyncSession,
    document_id: uuid.UUID,
    current_user: User,
    id_serie_override: Optional[str] = None,
) -> ImportDocument:
    """Send the comprovation document (PDF) to SEI as Tipo=R."""
    result = await db.execute(
        select(ImportDocument).where(ImportDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    if document.send_to_sei_status == DocSendStatus.SENT:
        # If content changed after sending, allow re-send by resetting the status
        if document.status and document.status.value in ("needs_reissue", "needs_update"):
            document.send_to_sei_status = DocSendStatus.NOT_SENT
            document.sei_document_number = None
            document.sei_document_id_legacy = None
            await db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Documento já enviado ao SEI "
                    f"(documento {document.sei_document_number or document.sei_document_id_legacy}). "
                    "Se precisar reenviar, regenere o comprovante primeiro para criar uma nova versão."
                ),
            )

    if not document.document_html:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conteúdo HTML do comprovante não disponível. Regenere o documento.",
        )

    sei_service = SEIService(db)
    config = await sei_service._get_config()
    if not sei_service._write_enabled(config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operações de escrita no SEI estão desabilitadas.",
        )

    proc_result = await db.execute(
        select(SEIProcess).where(SEIProcess.id == document.sei_process_id)
    )
    process = proc_result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo SEI não encontrado")

    document.send_to_sei_status = DocSendStatus.PENDING
    document.send_to_sei_error = None
    await db.flush()

    data_doc = (document.created_at or datetime.utcnow()).strftime("%d/%m/%Y")
    req_summary = {
        "operation": "incluirDocumento_comprovacao",
        "processo": process.numero_processo,
        "document_id": str(document_id),
    }
    try:
        result_doc = await sei_service.incluir_documento_comprovacao(
            numero_processo=process.numero_processo,
            html_content=document.document_html,
            nivel_acesso="publico",
            id_serie_override=id_serie_override,
        )
    except Exception as e:
        err = str(e)[:500]
        document.send_to_sei_status = DocSendStatus.ERROR
        document.send_to_sei_error = err
        await db.flush()
        await _record_write_op(
            db, current_user.id, "document", str(document_id),
            "incluirDocumentoComprovacao", "error",
            request_summary=req_summary, error_message=err,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Falha ao enviar documento ao SEI: {err}")

    document.sei_file_id = None  # Tipo=G does not use adicionarArquivo
    document.sei_document_id_legacy = result_doc.get("id_documento")
    document.sei_document_number = result_doc.get("documento_formatado")
    document.sei_document_link = result_doc.get("link_acesso")
    document.sent_to_sei_at = datetime.utcnow()
    document.send_to_sei_status = DocSendStatus.SENT
    document.send_to_sei_error = None
    document.status = DocumentStatus.SENT_TO_SEI
    document.sei_protocol = result_doc.get("documento_formatado")
    await db.flush()

    await _record_write_op(
        db, current_user.id, "document", str(document_id),
        "incluirDocumentoComprovacao", "success",
        request_summary=req_summary,
        response_summary={
            "id_documento": result_doc.get("id_documento"),
            "documento_formatado": result_doc.get("documento_formatado"),
        },
    )

    # Rebuild to stamp final content hash (force=True so sent SEI info appears in HTML)
    try:
        from app.services.document_service import rebuild_import_document_content
        await rebuild_import_document_content(db, document, force=True)
        # Preserve SENT_TO_SEI status — rebuild may have set NEEDS_REISSUE incorrectly
        # since we just updated the hash; re-stamp it
        document.status = DocumentStatus.SENT_TO_SEI
        await db.flush()
    except Exception as exc:
        logger.warning("Post-send rebuild failed (non-fatal): %s", exc)

    await db.refresh(document)
    return document
