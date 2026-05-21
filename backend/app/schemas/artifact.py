from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from app.models.artifact import ArtifactType, AccessLevel, ArtifactStatus, SendToSEIStatus


class ArtifactCreate(BaseModel):
    sei_process_id: UUID
    tipo_artefato: ArtifactType
    identificador_compras: str
    nivel_acesso: AccessLevel
    observacao: Optional[str] = None

    @field_validator("identificador_compras")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Identificador do Compras.gov.br é obrigatório")
        if len(v) > 255:
            raise ValueError("Identificador muito longo")
        return v


class ArtifactResponse(BaseModel):
    id: UUID
    sei_process_id: UUID
    user_id: UUID
    tipo_artefato: ArtifactType
    identificador_compras: str
    nivel_acesso: AccessLevel
    original_filename: str
    mime_type: str
    file_size: int
    sha256_hash: str
    md5_hash: str
    status: ArtifactStatus
    observacao: Optional[str]
    document_locked: bool
    created_at: datetime

    # SEI send tracking
    sei_file_id: Optional[str] = None
    sei_document_id: Optional[str] = None
    sei_document_number: Optional[str] = None
    sei_document_link: Optional[str] = None
    sent_to_sei_at: Optional[datetime] = None
    send_to_sei_status: SendToSEIStatus = SendToSEIStatus.NOT_SENT
    send_to_sei_error: Optional[str] = None

    model_config = {"from_attributes": True}


class ArtifactSendToSEIRequest(BaseModel):
    id_serie_override: Optional[str] = None


class ArtifactDeleteResponse(BaseModel):
    message: str
    artifact_id: UUID
    deleted_at: datetime
