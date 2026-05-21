from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Any
from app.models.sei_process import QueryStatus
import re


class SEIQueryRequest(BaseModel):
    numero_processo: str

    @field_validator("numero_processo")
    @classmethod
    def validate_process_number(cls, v: str) -> str:
        v = v.strip()
        # Accept formats like: 23298.000001/2024-01 or 23298.0001/2024-01
        pattern = r"^\d{5}\.\d{6}/\d{4}-\d{2}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Número de processo inválido. Formato esperado: NNNNN.NNNNNN/AAAA-NN"
            )
        return v


class UltimoAndamento(BaseModel):
    data_hora: Optional[str] = None
    unidade_sigla: Optional[str] = None
    descricao: Optional[str] = None


class SEIProcessResponse(BaseModel):
    id: UUID
    query_id: UUID
    id_procedimento: Optional[str]
    numero_processo: str
    especificacao: Optional[str]
    data_autuacao: Optional[str]
    link_acesso: Optional[str]
    nivel_acesso_local: Optional[str]
    nivel_acesso_global: Optional[str]
    tipo_procedimento_id: Optional[str]
    tipo_procedimento_nome: Optional[str]
    unidade_sigla: Optional[str]
    unidade_descricao: Optional[str]
    ultimo_andamento: Optional[Any]  # Parsed JSON
    created_at: datetime
    artifacts_count: Optional[int] = 0
    documents_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class SEIQueryResponse(BaseModel):
    id: UUID
    user_id: UUID
    numero_processo: str
    status: QueryStatus
    response_summary: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    process: Optional[SEIProcessResponse] = None

    model_config = {"from_attributes": True}


class SEIProcessListItem(BaseModel):
    id: UUID
    numero_processo: str
    especificacao: Optional[str]
    tipo_procedimento_nome: Optional[str]
    unidade_sigla: Optional[str]
    data_autuacao: Optional[str]
    created_at: datetime
    artifacts_count: int = 0

    model_config = {"from_attributes": True}
