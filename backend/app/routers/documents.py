import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import io
import os
import aiofiles
from app.database import get_db
from app.models.document import ImportDocument, DocumentStatus
from app.models.sei_process import SEIProcess
from app.models.user import User
from app.core.deps import get_current_user, get_client_ip
from app.schemas.document import DocumentCreate, DocumentResponse, DocumentListItem, DocumentSendToSEIRequest
from app.services.document_service import generate_document, rebuild_import_document_content
from app.services.sei_send_service import send_document_to_sei
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documentos de Comprovação"])


@router.post("/generate", response_model=DocumentResponse)
async def create_document(
    body: DocumentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get-or-create the single consolidated comprovante for this process and rebuild its content."""
    logger.info("GERAR COMPROVAÇÃO  processo=%s  user=%s", body.sei_process_id, current_user.email)
    document = await generate_document(db, body.sei_process_id, current_user)
    logger.info("COMPROVAÇÃO OK  doc_id=%s  status=%s  versão=%s", document.id, document.status, document.version_number)

    await log_action(
        db,
        action="DOCUMENT_GENERATED",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(document.id),
        ip_address=get_client_ip(request),
        metadata={"sei_process_id": str(body.sei_process_id), "version": document.version_number},
    )
    return DocumentResponse.from_orm_doc(document)


@router.get("/", response_model=list[DocumentListItem])
async def list_documents(
    sei_process_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    query = select(ImportDocument)
    if sei_process_id:
        query = query.where(ImportDocument.sei_process_id == sei_process_id)
    query = query.order_by(ImportDocument.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    docs = result.scalars().all()

    items = []
    for doc in docs:
        proc_result = await db.execute(
            select(SEIProcess.numero_processo).where(SEIProcess.id == doc.sei_process_id)
        )
        numero = proc_result.scalar_one_or_none()
        user_result = await db.execute(
            select(User.name).where(User.id == doc.user_id)
        )
        user_name = user_result.scalar_one_or_none()
        items.append(DocumentListItem(
            id=doc.id,
            sei_process_id=doc.sei_process_id,
            numero_processo=numero,
            user_id=doc.user_id,
            user_name=user_name,
            status=doc.status,
            created_at=doc.created_at,
            send_to_sei_status=doc.send_to_sei_status,
            sei_document_number=doc.sei_document_number,
            last_rebuilt_at=doc.last_rebuilt_at,
            version_number=doc.version_number,
        ))
    return items


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ImportDocument).where(ImportDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")
    resp = DocumentResponse.from_orm_doc(doc)
    resp.document_html = doc.document_html
    return resp


@router.get("/{doc_id}/html")
async def get_document_html(
    doc_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ImportDocument).where(ImportDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    await log_action(
        db,
        action="DOCUMENT_VIEWED",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(doc_id),
        ip_address=get_client_ip(request),
    )
    return HTMLResponse(content=doc.document_html)


@router.get("/{doc_id}/pdf")
async def download_document_pdf(
    doc_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ImportDocument).where(ImportDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")
    if not doc.pdf_path or not os.path.exists(doc.pdf_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF não disponível")

    async with aiofiles.open(doc.pdf_path, "rb") as f:
        content = await f.read()

    await log_action(
        db,
        action="DOCUMENT_PDF_DOWNLOADED",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(doc_id),
        ip_address=get_client_ip(request),
    )

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="comprovacao_{doc_id}.pdf"'},
    )


@router.post("/{doc_id}/rebuild", response_model=DocumentResponse)
async def rebuild_document(
    doc_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force-rebuild the consolidated comprovante content from current artifacts and audit logs."""
    result = await db.execute(select(ImportDocument).where(ImportDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    doc = await rebuild_import_document_content(db, doc, force=True)
    await log_action(
        db,
        action="DOCUMENT_REBUILT",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(doc_id),
        ip_address=get_client_ip(request),
        metadata={"version": doc.version_number},
    )
    return DocumentResponse.from_orm_doc(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Hard-delete the comprovation document. Allows re-generating a fresh one afterward.
    Logs deletion before removing. Does NOT remove anything from SEI.
    """
    result = await db.execute(select(ImportDocument).where(ImportDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    await log_action(
        db,
        action="DOCUMENT_DELETED",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(doc_id),
        ip_address=get_client_ip(request),
        metadata={
            "sei_process_id": str(doc.sei_process_id),
            "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
            "send_to_sei_status": doc.send_to_sei_status.value if hasattr(doc.send_to_sei_status, "value") else str(doc.send_to_sei_status),
            "sei_document_number": doc.sei_document_number,
            "version_number": doc.version_number,
        },
    )
    await db.delete(doc)
    await db.flush()


@router.post("/{doc_id}/send-to-sei", response_model=DocumentResponse)
async def send_document_to_sei_endpoint(
    doc_id: UUID,
    body: DocumentSendToSEIRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send the comprovation document PDF to SEI (adicionarArquivo + incluirDocumento Tipo=R).
    Idempotent: returns 409 if already sent. If content changed after send, returns 409 with needs_reissue message.
    """
    logger.info("SEND-TO-SEI COMPROVAÇÃO  doc_id=%s  user=%s  id_serie_override=%s", doc_id, current_user.email, body.id_serie_override)
    document = await send_document_to_sei(
        db, doc_id, current_user, id_serie_override=body.id_serie_override
    )
    logger.info("SEND-TO-SEI COMPROVAÇÃO OK  doc_id=%s  doc_sei=%s", doc_id, document.sei_document_number)
    await log_action(
        db,
        action="DOCUMENT_SENT_TO_SEI",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(doc_id),
        ip_address=get_client_ip(request),
        metadata={"sei_document_number": document.sei_document_number},
    )
    return DocumentResponse.from_orm_doc(document)
