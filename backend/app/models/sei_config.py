import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SEIConfig(Base):
    __tablename__ = "sei_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    soap_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sigla_sistema: Mapped[str] = mapped_column(String(50), nullable=False)
    # Encrypted with Fernet — never store plaintext
    identificacao_servico_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    id_unidade_default: Mapped[str] = mapped_column(String(50), nullable=False)
    sin_retornar_assuntos: Mapped[bool] = mapped_column(Boolean, default=True)
    sin_retornar_interessados: Mapped[bool] = mapped_column(Boolean, default=True)
    sin_retornar_observacoes: Mapped[bool] = mapped_column(Boolean, default=True)
    sin_retornar_ultimo_andamento: Mapped[bool] = mapped_column(Boolean, default=True)
    sin_retornar_unidades: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Write operation settings (added in migration 002)
    enable_write_operations: Mapped[bool] = mapped_column(Boolean, default=False)
    external_document_series_id: Mapped[str | None] = mapped_column(String(50))
    confirmation_document_series_id: Mapped[str | None] = mapped_column(String(50))
    tipo_conferencia_id: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
