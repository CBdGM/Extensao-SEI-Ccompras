import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

_vc = lambda x: [e.value for e in x]  # noqa: E731


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    SENT_TO_SEI = "sent_to_sei"
    NEEDS_UPDATE = "needs_update"
    NEEDS_REISSUE = "needs_reissue"
    REISSUED = "reissued"
    CANCELLED = "cancelled"
    ERROR = "error"


class SendToSEIStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    PENDING = "pending"
    FILE_UPLOADED_DOCUMENT_FAILED = "file_uploaded_document_failed"
    SENT = "sent"
    ERROR = "error"


class ImportDocument(Base):
    __tablename__ = "import_documents"
    __table_args__ = (
        UniqueConstraint("sei_process_id", name="uq_import_document_per_process"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sei_process_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sei_processes.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, values_callable=_vc, name="documentstatus", create_type=False),
        default=DocumentStatus.DRAFT,
    )
    sei_protocol: Mapped[str | None] = mapped_column(String(100))
    sei_document_id_legacy: Mapped[str | None] = mapped_column("sei_document_id", String(100))

    # SEI write-operation tracking
    sei_file_id: Mapped[str | None] = mapped_column(String(100))
    sei_document_number: Mapped[str | None] = mapped_column(String(100))
    sei_document_link: Mapped[str | None] = mapped_column(Text)
    sent_to_sei_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_to_sei_status: Mapped[SendToSEIStatus] = mapped_column(
        SAEnum(SendToSEIStatus, values_callable=_vc, name="sendtoseistatus", create_type=False),
        default=SendToSEIStatus.NOT_SENT,
    )
    send_to_sei_error: Mapped[str | None] = mapped_column(Text)

    # Content tracking
    last_rebuilt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_content_hash: Mapped[str | None] = mapped_column(String(64))
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    sei_process = relationship("SEIProcess", back_populates="documents")
    user = relationship("User", back_populates="documents")
