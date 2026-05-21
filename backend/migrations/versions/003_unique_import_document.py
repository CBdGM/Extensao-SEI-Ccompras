"""Unique import document per SEI process — new status values and tracking columns

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── Extend documentstatus enum with new values ────────────────────────────
    # PostgreSQL ALTER TYPE ADD VALUE cannot run inside a transaction,
    # so we recreate the type using a safe rename dance.
    conn.execute(sa.text("""
        CREATE TYPE documentstatus_new AS ENUM (
            'draft',
            'generated',
            'sent_to_sei',
            'needs_update',
            'needs_reissue',
            'reissued',
            'cancelled',
            'error'
        )
    """))
    conn.execute(sa.text("""
        ALTER TABLE import_documents
            ALTER COLUMN status TYPE documentstatus_new
            USING status::text::documentstatus_new
    """))
    conn.execute(sa.text("DROP TYPE documentstatus"))
    conn.execute(sa.text("ALTER TYPE documentstatus_new RENAME TO documentstatus"))

    # ── New tracking columns on import_documents ──────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE import_documents ADD COLUMN last_rebuilt_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE import_documents ADD COLUMN last_content_hash VARCHAR(64)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE import_documents ADD COLUMN version_number INTEGER NOT NULL DEFAULT 1"
    ))

    # ── Deduplicate before adding UNIQUE constraint ───────────────────────────
    # Keep the row with the latest created_at for each sei_process_id
    conn.execute(sa.text("""
        DELETE FROM import_documents
        WHERE id NOT IN (
            SELECT DISTINCT ON (sei_process_id) id
            FROM import_documents
            ORDER BY sei_process_id, created_at DESC
        )
    """))

    # ── Unique constraint: one import_document per SEI process ────────────────
    conn.execute(sa.text("""
        ALTER TABLE import_documents
            ADD CONSTRAINT uq_import_document_per_process UNIQUE (sei_process_id)
    """))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text(
        "ALTER TABLE import_documents DROP CONSTRAINT IF EXISTS uq_import_document_per_process"
    ))
    for col in ("last_rebuilt_at", "last_content_hash", "version_number"):
        conn.execute(sa.text(f"ALTER TABLE import_documents DROP COLUMN IF EXISTS {col}"))

    # Restore original 3-value enum
    conn.execute(sa.text("""
        CREATE TYPE documentstatus_old AS ENUM ('generated', 'sent_to_sei', 'cancelled')
    """))
    conn.execute(sa.text("""
        ALTER TABLE import_documents
            ALTER COLUMN status TYPE documentstatus_old
            USING CASE
                WHEN status::text IN ('generated','sent_to_sei','cancelled') THEN status::text
                ELSE 'generated'
            END::documentstatus_old
    """))
    conn.execute(sa.text("DROP TYPE documentstatus"))
    conn.execute(sa.text("ALTER TYPE documentstatus_old RENAME TO documentstatus"))
