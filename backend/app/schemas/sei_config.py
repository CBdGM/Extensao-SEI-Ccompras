from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional


class SEIConfigCreate(BaseModel):
    soap_url: str
    sigla_sistema: str
    identificacao_servico: str  # Plaintext input — encrypted before persisting
    id_unidade_default: str
    sin_retornar_assuntos: bool = True
    sin_retornar_interessados: bool = True
    sin_retornar_observacoes: bool = True
    sin_retornar_ultimo_andamento: bool = True
    sin_retornar_unidades: bool = True
    # Write operation settings
    enable_write_operations: bool = False
    external_document_series_id: Optional[str] = None
    confirmation_document_series_id: Optional[str] = None
    tipo_conferencia_id: Optional[str] = None

    @field_validator("soap_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL SOAP inválida")
        return v

    @field_validator("identificacao_servico")
    @classmethod
    def service_key_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Chave de acesso não pode ser vazia")
        return v


class SEIConfigUpdate(SEIConfigCreate):
    identificacao_servico: Optional[str] = None  # Optional on update


class SEIConfigResponse(BaseModel):
    id: UUID
    soap_url: str
    sigla_sistema: str
    id_unidade_default: str
    sin_retornar_assuntos: bool
    sin_retornar_interessados: bool
    sin_retornar_observacoes: bool
    sin_retornar_ultimo_andamento: bool
    sin_retornar_unidades: bool
    is_active: bool
    enable_write_operations: bool
    external_document_series_id: Optional[str]
    confirmation_document_series_id: Optional[str]
    tipo_conferencia_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    # NOTE: identificacao_servico is NEVER returned to client

    model_config = {"from_attributes": True}


class SEIWriteStatusResponse(BaseModel):
    """Returned by GET /sei-config/write-status to inform the frontend."""
    write_enabled: bool
    source: str  # "env" | "db_config" | "disabled"
    external_series_configured: bool
    confirmation_series_configured: bool
