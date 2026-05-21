"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("CREATE TYPE userrole AS ENUM ('admin', 'user')"))
    conn.execute(sa.text("CREATE TYPE querystatus AS ENUM ('success', 'error', 'pending')"))
    conn.execute(sa.text("CREATE TYPE artifacttype AS ENUM ('DFD', 'ETP', 'TR', 'MATRIZ_RISCOS')"))
    conn.execute(sa.text("CREATE TYPE accesslevel AS ENUM ('publico', 'restrito', 'sigiloso')"))
    conn.execute(sa.text("CREATE TYPE artifactstatus AS ENUM ('active', 'deleted')"))
    conn.execute(sa.text("CREATE TYPE documentstatus AS ENUM ('generated', 'sent_to_sei', 'cancelled')"))

    conn.execute(sa.text("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role userrole NOT NULL DEFAULT 'user',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX ix_users_email ON users(email)"))

    conn.execute(sa.text("""
        CREATE TABLE sei_config (
            id UUID PRIMARY KEY,
            soap_url VARCHAR(500) NOT NULL,
            sigla_sistema VARCHAR(50) NOT NULL,
            identificacao_servico_encrypted TEXT NOT NULL,
            id_unidade_default VARCHAR(50) NOT NULL,
            sin_retornar_assuntos BOOLEAN DEFAULT true,
            sin_retornar_interessados BOOLEAN DEFAULT true,
            sin_retornar_observacoes BOOLEAN DEFAULT true,
            sin_retornar_ultimo_andamento BOOLEAN DEFAULT true,
            sin_retornar_unidades BOOLEAN DEFAULT true,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE sei_process_queries (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            numero_processo VARCHAR(50) NOT NULL,
            status querystatus NOT NULL,
            response_summary TEXT,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX ix_sei_process_queries_numero ON sei_process_queries(numero_processo)"))

    conn.execute(sa.text("""
        CREATE TABLE sei_processes (
            id UUID PRIMARY KEY,
            query_id UUID NOT NULL REFERENCES sei_process_queries(id),
            id_procedimento VARCHAR(50) NOT NULL,
            numero_processo VARCHAR(50) NOT NULL,
            especificacao TEXT,
            data_autuacao VARCHAR(50),
            link_acesso TEXT,
            nivel_acesso_local VARCHAR(50),
            nivel_acesso_global VARCHAR(50),
            tipo_procedimento_id VARCHAR(50),
            tipo_procedimento_nome VARCHAR(255),
            unidade_sigla VARCHAR(50),
            unidade_descricao VARCHAR(255),
            ultimo_andamento TEXT,
            raw_response_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX ix_sei_processes_numero ON sei_processes(numero_processo)"))
    conn.execute(sa.text("CREATE INDEX ix_sei_processes_id_proc ON sei_processes(id_procedimento)"))

    conn.execute(sa.text("""
        CREATE TABLE imported_artifacts (
            id UUID PRIMARY KEY,
            sei_process_id UUID NOT NULL REFERENCES sei_processes(id),
            user_id UUID NOT NULL REFERENCES users(id),
            tipo_artefato artifacttype NOT NULL,
            identificador_compras VARCHAR(255) NOT NULL,
            nivel_acesso accesslevel NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            file_size BIGINT NOT NULL,
            sha256_hash VARCHAR(64) NOT NULL,
            md5_hash VARCHAR(32) NOT NULL,
            storage_path VARCHAR(500) NOT NULL,
            status artifactstatus NOT NULL DEFAULT 'active',
            observacao TEXT,
            document_locked BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ,
            deleted_by UUID
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE import_documents (
            id UUID PRIMARY KEY,
            sei_process_id UUID NOT NULL REFERENCES sei_processes(id),
            user_id UUID NOT NULL REFERENCES users(id),
            document_html TEXT NOT NULL,
            pdf_path VARCHAR(500),
            status documentstatus NOT NULL,
            sei_protocol VARCHAR(100),
            sei_document_id VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id),
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(100),
            entity_id VARCHAR(100),
            ip_address VARCHAR(45),
            user_agent TEXT,
            metadata_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX ix_audit_logs_action ON audit_logs(action)"))
    conn.execute(sa.text("CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at)"))
    conn.execute(sa.text("CREATE INDEX ix_audit_logs_entity_type ON audit_logs(entity_type)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS audit_logs"))
    conn.execute(sa.text("DROP TABLE IF EXISTS import_documents"))
    conn.execute(sa.text("DROP TABLE IF EXISTS imported_artifacts"))
    conn.execute(sa.text("DROP TABLE IF EXISTS sei_processes"))
    conn.execute(sa.text("DROP TABLE IF EXISTS sei_process_queries"))
    conn.execute(sa.text("DROP TABLE IF EXISTS sei_config"))
    conn.execute(sa.text("DROP TABLE IF EXISTS users"))
    conn.execute(sa.text("DROP TYPE IF EXISTS documentstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS artifactstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS accesslevel"))
    conn.execute(sa.text("DROP TYPE IF EXISTS artifacttype"))
    conn.execute(sa.text("DROP TYPE IF EXISTS querystatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS userrole"))
