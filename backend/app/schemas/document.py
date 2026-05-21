from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional
from app.models.document import DocumentStatus, SendToSEIStatus


class DocumentCreate(BaseModel):
    sei_process_id: UUID


class DocumentSendToSEIRequest(BaseModel):
    id_serie_override: Optional[str] = None


class DocumentResponse(BaseModel):
    id: UUID
    sei_process_id: UUID
    user_id: UUID
    status: DocumentStatus
    sei_protocol: Optional[str]
    created_at: datetime
    document_html: Optional[str] = None

    # SEI send tracking
    sei_file_id: Optional[str] = None
    sei_document_id: Optional[str] = None
    sei_document_number: Optional[str] = None
    sei_document_link: Optional[str] = None
    sent_to_sei_at: Optional[datetime] = None
    send_to_sei_status: SendToSEIStatus = SendToSEIStatus.NOT_SENT
    send_to_sei_error: Optional[str] = None

    # Content tracking
    last_rebuilt_at: Optional[datetime] = None
    last_content_hash: Optional[str] = None
    version_number: int = 1

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_doc(cls, doc) -> "DocumentResponse":
        return cls(
            id=doc.id,
            sei_process_id=doc.sei_process_id,
            user_id=doc.user_id,
            status=doc.status,
            sei_protocol=doc.sei_protocol,
            created_at=doc.created_at,
            sei_file_id=doc.sei_file_id,
            sei_document_id=doc.sei_document_id_legacy,
            sei_document_number=doc.sei_document_number,
            sei_document_link=doc.sei_document_link,
            sent_to_sei_at=doc.sent_to_sei_at,
            send_to_sei_status=doc.send_to_sei_status,
            send_to_sei_error=doc.send_to_sei_error,
            last_rebuilt_at=doc.last_rebuilt_at,
            last_content_hash=doc.last_content_hash,
            version_number=doc.version_number or 1,
        )


class DocumentListItem(BaseModel):
    id: UUID
    sei_process_id: UUID
    numero_processo: Optional[str] = None
    user_id: UUID
    user_name: Optional[str] = None
    status: DocumentStatus
    send_to_sei_status: SendToSEIStatus = SendToSEIStatus.NOT_SENT
    sei_document_number: Optional[str] = None
    last_rebuilt_at: Optional[datetime] = None
    version_number: int = 1
    created_at: datetime

    model_config = {"from_attributes": True}
