import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from uuid import UUID
from typing import Optional
from app.database import get_db
from app.models.audit import AuditLog
from app.models.artifact import ImportedArtifact
from app.models.document import ImportDocument
from app.models.user import User
from app.core.deps import require_admin, get_current_user
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Auditoria"])


@router.get("/", response_model=list[AuditLogResponse])
async def list_audit_logs(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    items = []
    for log in logs:
        user_name = None
        if log.user_id:
            user_result = await db.execute(
                select(User.name).where(User.id == log.user_id)
            )
            user_name = user_result.scalar_one_or_none()

        parsed_meta = None
        if log.metadata_json:
            try:
                parsed_meta = json.loads(log.metadata_json)
            except Exception:
                parsed_meta = log.metadata_json

        items.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_name=user_name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=log.ip_address,
            metadata_json=parsed_meta,
            created_at=log.created_at,
        ))
    return items


@router.get("/process/{process_id}", response_model=list[AuditLogResponse])
async def list_process_audit_logs(
    process_id: UUID,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return audit trail for a process and all its artifacts/documents. Admin only."""
    # Collect all entity IDs related to this process
    entity_ids = {str(process_id)}

    art_result = await db.execute(
        select(ImportedArtifact.id).where(ImportedArtifact.sei_process_id == process_id)
    )
    for (art_id,) in art_result.all():
        entity_ids.add(str(art_id))

    doc_result = await db.execute(
        select(ImportDocument.id).where(ImportDocument.sei_process_id == process_id)
    )
    for (doc_id,) in doc_result.all():
        entity_ids.add(str(doc_id))

    logs_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id.in_(entity_ids))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = logs_result.scalars().all()

    items = []
    for log in logs:
        user_name = None
        if log.user_id:
            user_result = await db.execute(select(User.name).where(User.id == log.user_id))
            user_name = user_result.scalar_one_or_none()
        parsed_meta = None
        if log.metadata_json:
            try:
                parsed_meta = json.loads(log.metadata_json)
            except Exception:
                parsed_meta = log.metadata_json
        items.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_name=user_name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=log.ip_address,
            metadata_json=parsed_meta,
            created_at=log.created_at,
        ))
    return items
