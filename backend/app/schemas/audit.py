from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, Any


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    user_name: Optional[str] = None
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    ip_address: Optional[str]
    metadata_json: Optional[Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogFilter(BaseModel):
    action: Optional[str] = None
    entity_type: Optional[str] = None
    user_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
