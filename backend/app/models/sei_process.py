import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class QueryStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class SEIProcessQuery(Base):
    __tablename__ = "sei_process_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    numero_processo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[QueryStatus] = mapped_column(
        SAEnum(QueryStatus, values_callable=lambda x: [e.value for e in x], name="querystatus", create_type=False),
        default=QueryStatus.PENDING,
    )
    response_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="queries")
    process = relationship("SEIProcess", back_populates="query", uselist=False)


class SEIProcess(Base):
    __tablename__ = "sei_processes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sei_process_queries.id"), nullable=False)
    id_procedimento: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    numero_processo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    especificacao: Mapped[str | None] = mapped_column(Text)
    data_autuacao: Mapped[str | None] = mapped_column(String(50))
    link_acesso: Mapped[str | None] = mapped_column(Text)
    nivel_acesso_local: Mapped[str | None] = mapped_column(String(50))
    nivel_acesso_global: Mapped[str | None] = mapped_column(String(50))
    tipo_procedimento_id: Mapped[str | None] = mapped_column(String(50))
    tipo_procedimento_nome: Mapped[str | None] = mapped_column(String(255))
    unidade_sigla: Mapped[str | None] = mapped_column(String(50))
    unidade_descricao: Mapped[str | None] = mapped_column(String(255))
    ultimo_andamento: Mapped[str | None] = mapped_column(Text)  # JSON
    raw_response_json: Mapped[str | None] = mapped_column(Text)  # Full JSON response
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    query = relationship("SEIProcessQuery", back_populates="process")
    artifacts = relationship("ImportedArtifact", back_populates="sei_process", lazy="select")
    documents = relationship("ImportDocument", back_populates="sei_process", lazy="select")
