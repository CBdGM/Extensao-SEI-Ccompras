"""SEI write operation columns

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Enum for send-to-SEI status used by artifacts and documents
    conn.execute(sa.text(
        "CREATE TYPE sendtoseistatus AS ENUM "
        "('not_sent','pending','file_uploaded_document_failed','sent','error')"
    ))

    # ── imported_artifacts new columns ────────────────────────────────────────
    conn.execute(sa.text("ALTER TABLE imported_artifacts ADD COLUMN sei_file_id VARCHAR(100)"))
    conn.execute(sa.text("ALTER TABLE imported_artifacts ADD COLUMN sei_document_id VARCHAR(100)"))
    conn.execute(sa.text("ALTER TABLE imported_artifacts ADD COLUMN sei_document_number VARCHAR(100)"))
    conn.execute(sa.text("ALTER TABLE imported_artifacts ADD COLUMN sei_document_link TEXT"))
    conn.execute(sa.text("ALTER TABLE imported_artifacts ADD COLUMN sent_to_sei_at TIMESTAMPTZ"))
    conn.execute(sa.text(
        "ALTER TABLE imported_artifacts ADD COLUMN send_to_sei_status sendtoseistatus NOT NULL DEFAULT 'not_sent'"
    ))
    conn.execute(sa.text("ALTER TABLE imported_artifacts ADD COLUMN send_to_sei_error TEXT"))

    # ── import_documents new columns ─────────────────────────────────────────
    # sei_document_id already exists from migration 001 (reused as sei_document_id_legacy in ORM)
    conn.execute(sa.text("ALTER TABLE import_documents ADD COLUMN sei_file_id VARCHAR(100)"))
    conn.execute(sa.text("ALTER TABLE import_documents ADD COLUMN sei_document_number VARCHAR(100)"))
    conn.execute(sa.text("ALTER TABLE import_documents ADD COLUMN sei_document_link TEXT"))
    conn.execute(sa.text("ALTER TABLE import_documents ADD COLUMN sent_to_sei_at TIMESTAMPTZ"))
    conn.execute(sa.text(
        "ALTER TABLE import_documents ADD COLUMN send_to_sei_status sendtoseistatus NOT NULL DEFAULT 'not_sent'"
    ))
    conn.execute(sa.text("ALTER TABLE import_documents ADD COLUMN send_to_sei_error TEXT"))

    # ── sei_config new columns for write operation settings ───────────────────
    conn.execute(sa.text("ALTER TABLE sei_config ADD COLUMN enable_write_operations BOOLEAN DEFAULT false"))
    conn.execute(sa.text("ALTER TABLE sei_config ADD COLUMN external_document_series_id VARCHAR(50)"))
    conn.execute(sa.text("ALTER TABLE sei_config ADD COLUMN confirmation_document_series_id VARCHAR(50)"))
    conn.execute(sa.text("ALTER TABLE sei_config ADD COLUMN tipo_conferencia_id VARCHAR(50)"))

    # ── sei_write_operations log table ────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE sei_write_operations (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id),
            entity_type VARCHAR(50) NOT NULL,
            entity_id VARCHAR(100) NOT NULL,
            operation VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            request_summary_json TEXT,
            response_summary_json TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX ix_sei_write_ops_entity ON sei_write_operations(entity_type, entity_id)"))
    conn.execute(sa.text("CREATE INDEX ix_sei_write_ops_created_at ON sei_write_operations(created_at)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS sei_write_operations"))

    for col in ("enable_write_operations", "external_document_series_id",
                "confirmation_document_series_id", "tipo_conferencia_id"):
        conn.execute(sa.text(f"ALTER TABLE sei_config DROP COLUMN IF EXISTS {col}"))

    for col in ("sei_file_id", "sei_document_number", "sei_document_link",
                "sent_to_sei_at", "send_to_sei_status", "send_to_sei_error"):
        conn.execute(sa.text(f"ALTER TABLE import_documents DROP COLUMN IF EXISTS {col}"))

    for col in ("sei_file_id", "sei_document_id", "sei_document_number", "sei_document_link",
                "sent_to_sei_at", "send_to_sei_status", "send_to_sei_error"):
        conn.execute(sa.text(f"ALTER TABLE imported_artifacts DROP COLUMN IF EXISTS {col}"))

    conn.execute(sa.text("DROP TYPE IF EXISTS sendtoseistatus"))
