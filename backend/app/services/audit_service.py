import json
import logging
from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Persist an audit event. Metadata must never include credentials or key material.
    This function is fire-and-forget — errors are logged but not raised to caller.
    """
    try:
        # Sanitize metadata — remove any accidental key fields
        if metadata:
            safe_meta = {
                k: v for k, v in metadata.items()
                if k.lower() not in {
                    "password", "senha", "chave", "key", "secret",
                    "token", "identificacao_servico", "credential",
                }
            }
        else:
            safe_meta = None

        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            metadata_json=json.dumps(safe_meta, default=str) if safe_meta else None,
        )
        db.add(entry)
        await db.flush()
    except Exception as e:
        logger.error("Audit log failed for action=%s: %s", action, type(e).__name__)
