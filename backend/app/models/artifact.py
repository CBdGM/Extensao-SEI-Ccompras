import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, BigInteger, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

_vc = lambda x: [e.value for e in x]  # noqa: E731


class ArtifactType(str, enum.Enum):
    DFD = "DFD"
    ETP = "ETP"
    TERMO_REFERENCIA = "TR"
    MATRIZ_RISCOS = "MATRIZ_RISCOS"


class AccessLevel(str, enum.Enum):
    PUBLICO = "publico"
    RESTRITO = "restrito"
    SIGILOSO = "sigiloso"


class ArtifactStatus(str, enum.Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class SendToSEIStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    PENDING = "pending"
    FILE_UPLOADED_DOCUMENT_FAILED = "file_uploaded_document_failed"
    SENT = "sent"
    ERROR = "error"


class ImportedArtifact(Base):
    __tablename__ = "imported_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sei_process_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sei_processes.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    tipo_artefato: Mapped[ArtifactType] = mapped_column(
        SAEnum(ArtifactType, values_callable=_vc, name="artifacttype", create_type=False),
        nullable=False,
    )
    identificador_compras: Mapped[str] = mapped_column(String(255), nullable=False)
    nivel_acesso: Mapped[AccessLevel] = mapped_column(
        SAEnum(AccessLevel, values_callable=_vc, name="accesslevel", create_type=False),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    md5_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ArtifactStatus] = mapped_column(
        SAEnum(ArtifactStatus, values_callable=_vc, name="artifactstatus", create_type=False),
        default=ArtifactStatus.ACTIVE,
    )
    observacao: Mapped[str | None] = mapped_column(Text)
    document_locked: Mapped[bool] = mapped_column(default=False)

    # SEI write-operation tracking
    sei_file_id: Mapped[str | None] = mapped_column(String(100))
    sei_document_id: Mapped[str | None] = mapped_column(String(100))
    sei_document_number: Mapped[str | None] = mapped_column(String(100))
    sei_document_link: Mapped[str | None] = mapped_column(Text)
    sent_to_sei_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_to_sei_status: Mapped[SendToSEIStatus] = mapped_column(
        SAEnum(SendToSEIStatus, values_callable=_vc, name="sendtoseistatus", create_type=False),
        default=SendToSEIStatus.NOT_SENT,
    )
    send_to_sei_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    sei_process = relationship("SEIProcess", back_populates="artifacts")
    user = relationship("User", back_populates="artifacts")
