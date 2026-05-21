"""
Document service — unique consolidated ImportDocument per SEI process.

Key functions:
  get_or_create_import_document  — returns the single comprovante for a process
  rebuild_import_document_content — regenerates HTML/PDF from current artifacts + audit logs
  generate_document               — public entry-point (get_or_create + rebuild)
"""
import hashlib
import json
import os
import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.config import settings
from app.models.document import ImportDocument, DocumentStatus, SendToSEIStatus
from app.models.sei_process import SEIProcess
from app.models.artifact import ImportedArtifact, ArtifactStatus, SendToSEIStatus as ArtifactSendStatus
from app.models.user import User
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

ARTIFACT_TYPE_LABELS = {
    "DFD": "Documento de Formalização de Demanda (DFD)",
    "ETP": "Estudo Técnico Preliminar (ETP)",
    "TR": "Termo de Referência",
    "MATRIZ_RISCOS": "Matriz de Riscos",
}

ACCESS_LEVEL_LABELS = {
    "publico": "Público",
    "restrito": "Restrito",
    "sigiloso": "Sigiloso",
}

SEI_SEND_LABELS = {
    "not_sent": "Não enviado",
    "pending": "Enviando…",
    "file_uploaded_document_failed": "Arquivo enviado / Documento falhou",
    "sent": "Enviado ao SEI",
    "error": "Erro",
}

ACTION_LABELS = {
    "ARTIFACT_UPLOADED": "Artefato importado no middleware",
    "ARTIFACT_DELETED": "Artefato removido",
    "ARTIFACT_SENT_TO_SEI": "Artefato enviado ao SEI",
    "ARTIFACT_DOWNLOADED": "Artefato baixado",
    "DOCUMENT_GENERATED": "Documento de comprovação gerado",
    "DOCUMENT_REBUILT": "Documento de comprovação atualizado",
    "DOCUMENT_SENT_TO_SEI": "Documento de comprovação enviado ao SEI",
    "DOCUMENT_VIEWED": "Documento visualizado",
    "DOCUMENT_PDF_DOWNLOADED": "PDF do documento baixado",
}


def _fmt(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _render_html(
    process: SEIProcess,
    artifacts: list,
    deleted_artifacts: list,
    audit_logs: list,
    doc: ImportDocument,
    users_by_id: dict,
    rebuilt_at: datetime,
) -> str:

    # ── Section 2: Artifacts table rows ──────────────────────────────────────
    def _artifact_row(i: int, a, deleted: bool) -> str:
        sei_doc = ""
        if a.sei_document_number:
            if a.sei_document_link:
                sei_doc = f'<a href="{a.sei_document_link}" target="_blank">{a.sei_document_number}</a>'
            else:
                sei_doc = a.sei_document_number
        status_label = SEI_SEND_LABELS.get(
            a.send_to_sei_status.value if hasattr(a.send_to_sei_status, "value") else str(a.send_to_sei_status),
            ""
        )
        user_name = users_by_id.get(str(a.user_id), "")
        row_style = ' style="background:#fff5f5;opacity:0.75;text-decoration:line-through"' if deleted else ""
        status_cell = (
            f'<span style="text-decoration:none;color:#c0392b;font-weight:bold">Removido em {_fmt(a.deleted_at)}</span>'
            if deleted else status_label
        )
        return f"""
        <tr{row_style}>
          <td class="center">{i}</td>
          <td>{ARTIFACT_TYPE_LABELS.get(a.tipo_artefato.value if hasattr(a.tipo_artefato, "value") else str(a.tipo_artefato), str(a.tipo_artefato))}</td>
          <td>{a.identificador_compras}</td>
          <td class="center">{sei_doc}</td>
          <td>{a.original_filename}</td>
          <td class="hash">{a.sha256_hash}</td>
          <td class="hash">{a.md5_hash}</td>
          <td>{ACCESS_LEVEL_LABELS.get(a.nivel_acesso.value if hasattr(a.nivel_acesso, "value") else str(a.nivel_acesso), str(a.nivel_acesso))}</td>
          <td style="text-decoration:none">{status_cell}</td>
          <td>{user_name}</td>
          <td>{_fmt(a.created_at)}</td>
          <td>{_fmt(a.sent_to_sei_at)}</td>
        </tr>"""

    artifact_rows = ""
    for i, a in enumerate(artifacts, 1):
        artifact_rows += _artifact_row(i, a, deleted=False)
    offset = len(artifacts)
    for i, a in enumerate(deleted_artifacts, offset + 1):
        artifact_rows += _artifact_row(i, a, deleted=True)

    total = len(artifacts) + len(deleted_artifacts)
    if not artifact_rows:
        artifact_rows = '<tr><td colspan="12" style="text-align:center;color:#888">Nenhum artefato importado.</td></tr>'

    # ── Section 3: Audit history rows ─────────────────────────────────────────
    audit_rows = ""
    for log in audit_logs:
        user_name = users_by_id.get(str(log.user_id), "") if log.user_id else "Sistema"
        action_label = ACTION_LABELS.get(log.action, log.action)
        meta = {}
        if log.metadata_json:
            try:
                meta = log.metadata_json if isinstance(log.metadata_json, dict) else json.loads(log.metadata_json)
            except Exception:
                meta = {}
        sha = meta.get("sha256", "")
        sei_doc_num = meta.get("sei_document_number", meta.get("documento_formatado", ""))
        obs_parts = []
        if meta.get("tipo_artefato"):
            obs_parts.append(f"Tipo: {meta['tipo_artefato']}")
        if meta.get("identificador_compras"):
            obs_parts.append(f"Compras: {meta['identificador_compras']}")
        if meta.get("original_filename") or meta.get("file"):
            obs_parts.append(f"Arquivo: {meta.get('original_filename', meta.get('file', ''))}")
        if meta.get("error"):
            obs_parts.append(f"Erro: {meta['error'][:80]}")
        obs = " | ".join(obs_parts)
        entity_ref = f"{log.entity_type}/{str(log.entity_id)[:8]}..." if log.entity_id else ""
        audit_rows += f"""
        <tr>
          <td>{_fmt(log.created_at)}</td>
          <td>{user_name}</td>
          <td>{action_label}</td>
          <td class="mono">{entity_ref}</td>
          <td class="hash">{sha}</td>
          <td class="center">{sei_doc_num}</td>
          <td>{obs}</td>
        </tr>"""

    if not audit_rows:
        audit_rows = '<tr><td colspan="7" style="text-align:center;color:#888">Sem eventos registrados.</td></tr>'

    version_info = f"v{doc.version_number}" if doc.version_number else "v1"
    sei_status_display = ""
    if doc.send_to_sei_status == SendToSEIStatus.SENT and doc.sei_document_number:
        link = f' (<a href="{doc.sei_document_link}" target="_blank">{doc.sei_document_number}</a>)' if doc.sei_document_link else f" ({doc.sei_document_number})"
        sei_status_display = f"<p style='color:#1a7a3c;margin-top:8px'>&#10003; Enviado ao SEI{link} em {_fmt(doc.sent_to_sei_at)}</p>"
    elif doc.send_to_sei_status == SendToSEIStatus.NOT_SENT:
        sei_status_display = "<p style='color:#666;margin-top:8px'>Ainda não enviado ao SEI.</p>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Comprovacao de Importacao - {process.numero_processo}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, sans-serif; font-size: 11px; color: #1a1a1a; background: #fff; padding: 32px; }}
    header {{ text-align: center; border-bottom: 3px solid #003366; padding-bottom: 16px; margin-bottom: 20px; }}
    header h1 {{ font-size: 14px; color: #003366; text-transform: uppercase; letter-spacing: 1px; }}
    header h2 {{ font-size: 12px; margin-top: 4px; }}
    header p {{ font-size: 10px; color: #666; margin-top: 3px; }}
    section {{ margin-bottom: 20px; }}
    section h3 {{ font-size: 12px; color: #003366; border-left: 4px solid #003366;
                  padding-left: 8px; margin-bottom: 10px; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
    table th {{ background: #003366; color: #fff; padding: 6px 8px; text-align: left; white-space: nowrap; }}
    table td {{ padding: 5px 8px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
    table tr:nth-child(even) td {{ background: #f8f8f8; }}
    .info-table td:first-child {{ font-weight: bold; width: 200px; color: #003366; }}
    .hash {{ font-family: monospace; font-size: 8px; word-break: break-all; }}
    .mono {{ font-family: monospace; font-size: 9px; }}
    .center {{ text-align: center; }}
    .declaration {{ background: #f0f4fa; border-left: 4px solid #003366; padding: 14px; line-height: 1.7; }}
    .declaration p + p {{ margin-top: 8px; }}
    footer {{ margin-top: 24px; padding-top: 12px; border-top: 1px solid #ccc;
              text-align: center; font-size: 9px; color: #888; }}
  </style>
</head>
<body>
  <header>
    <h1>Instituto Federal de Educa&#231;&#227;o, Ci&#234;ncia e Tecnologia de Pernambuco &mdash; IFPE</h1>
    <h2>Documento de Comprova&#231;&#227;o de Importa&#231;&#227;o de Artefatos do Compras.gov.br</h2>
    <p>Sistema de Integra&#231;&#227;o Compras.gov.br &rarr; SEI | {version_info} | &#218;ltima atualiza&#231;&#227;o: {_fmt(rebuilt_at)}</p>
  </header>

  <!-- Seção 1 — Dados do Processo -->
  <section>
    <h3>1. Dados do Processo SEI</h3>
    <table class="info-table">
      <tr><td>Número do Processo:</td><td><strong>{process.numero_processo}</strong></td></tr>
      <tr><td>Tipo do Processo:</td><td>{process.tipo_procedimento_nome or ''}</td></tr>
      <tr><td>Especifica&#231;&#227;o:</td><td>{process.especificacao or ''}</td></tr>
      <tr><td>Unidade:</td><td>{(process.unidade_descricao or '') + (' (' + process.unidade_sigla + ')' if process.unidade_sigla else '')}</td></tr>
      <tr><td>Data de Autua&#231;&#227;o:</td><td>{process.data_autuacao or ''}</td></tr>
      <tr><td>N&#237;vel de Acesso:</td><td>{process.nivel_acesso_local or ''}</td></tr>
      <tr><td>ID do Comprovante:</td><td class="mono">{doc.id}</td></tr>
      <tr><td>Vers&#227;o:</td><td>{version_info}</td></tr>
      <tr><td>Gerado em:</td><td>{_fmt(doc.created_at)}</td></tr>
      <tr><td>&#218;ltima atualiza&#231;&#227;o:</td><td>{_fmt(rebuilt_at)}</td></tr>
      <tr><td>Status SEI:</td><td>{sei_status_display}</td></tr>
    </table>
  </section>

  <!-- Secao 2 - Artefatos Importados -->
  <section>
    <h3>2. Artefatos Importados ({len(artifacts)} ativo(s){f", {len(deleted_artifacts)} removido(s)" if deleted_artifacts else ""})</h3>
    <table>
      <thead>
        <tr>
          <th>N&#186;</th><th>Tipo</th><th>Identificador Compras</th><th>Doc SEI</th>
          <th>Nome do Arquivo</th><th>SHA-256</th><th>MD5</th>
          <th>Acesso</th><th>Status SEI</th><th>Importado por</th>
          <th>Data Importa&#231;&#227;o</th><th>Enviado ao SEI</th>
        </tr>
      </thead>
      <tbody>{artifact_rows}</tbody>
    </table>
  </section>

  <!-- Secao 3 - Historico -->
  <section>
    <h3>3. Hist&#243;rico de Modifica&#231;&#245;es e Envios</h3>
    <table>
      <thead>
        <tr>
          <th>Data/Hora</th><th>Usu&#225;rio</th><th>A&#231;&#227;o</th><th>Entidade</th>
          <th>SHA-256</th><th>Doc SEI</th><th>Observa&#231;&#227;o</th>
        </tr>
      </thead>
      <tbody>{audit_rows}</tbody>
    </table>
  </section>

  <!-- Secao 4 - Declaracao -->
  <section>
    <h3>4. Declara&#231;&#227;o de Autenticidade e Rastreabilidade</h3>
    <div class="declaration">
      <p>Este documento consolida o registro de importa&#231;&#227;o dos artefatos t&#233;cnicos oriundos do
      <strong>Compras.gov.br</strong> vinculados ao processo SEI <strong>{process.numero_processo}</strong>,
      com a finalidade de preservar a rastreabilidade, a integridade e a origem dos documentos importados.</p>
      <p>Os hashes <strong>SHA-256</strong> e <strong>MD5</strong> registrados garantem a integridade de cada
      arquivo, permitindo verificar em qualquer momento que os arquivos n&#227;o foram alterados ap&#243;s a importa&#231;&#227;o.
      Cada opera&#231;&#227;o realizada &#233; registrada no hist&#243;rico de modifica&#231;&#245;es acima.</p>
      <p>Este documento &#233; &#250;nico por processo SEI e atualizado automaticamente sempre que novos artefatos s&#227;o
      importados ou modificados. Em conformidade com os requisitos de auditoria da
      <strong>Lei n&#186; 14.133/2021</strong> (Nova Lei de Licita&#231;&#245;es).</p>
    </div>
  </section>

  <footer>
    <p>Documento de Comprova&#231;&#227;o - Processo {process.numero_processo} - {version_info}</p>
    <p>Gerado pelo Sistema de Integra&#231;&#227;o Compras-SEI (MVP) - IFPE | &#218;ltima atualiza&#231;&#227;o: {_fmt(rebuilt_at)}</p>
    <p>Hash do conte&#250;do deste documento: <span class="hash">{_sha256(process.numero_processo + str(len(artifacts)) + _fmt(rebuilt_at))}</span></p>
  </footer>
</body>
</html>"""


async def _load_users_by_id(db: AsyncSession, user_ids: set) -> dict:
    if not user_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    return {str(u.id): u.name for u in result.scalars().all()}


async def get_or_create_import_document(
    db: AsyncSession,
    sei_process_id: uuid.UUID,
    current_user: User,
) -> tuple[ImportDocument, bool]:
    """Return (document, created). Guarantees at most one document per process."""
    result = await db.execute(
        select(ImportDocument).where(ImportDocument.sei_process_id == sei_process_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    doc = ImportDocument(
        sei_process_id=sei_process_id,
        user_id=current_user.id,
        document_html="",
        status=DocumentStatus.DRAFT,
        version_number=1,
    )
    db.add(doc)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(ImportDocument).where(ImportDocument.sei_process_id == sei_process_id)
        )
        existing = result.scalar_one_or_none()
        return existing, False

    await db.refresh(doc)
    return doc, True


async def rebuild_import_document_content(
    db: AsyncSession,
    document: ImportDocument,
    force: bool = False,
) -> ImportDocument:
    """Regenerate HTML + PDF from current artifacts and audit history.

    If the content hash is unchanged and force=False, returns early without writing.
    If the document was already sent to SEI and content changed, marks NEEDS_REISSUE.
    """
    # ── Fetch process ─────────────────────────────────────────────────────────
    proc_result = await db.execute(
        select(SEIProcess).where(SEIProcess.id == document.sei_process_id)
    )
    process = proc_result.scalar_one_or_none()
    if not process:
        logger.warning("rebuild_import_document_content: process %s not found", document.sei_process_id)
        return document

    # ── Fetch active and deleted artifacts ───────────────────────────────────
    art_result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.sei_process_id == document.sei_process_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        ).order_by(ImportedArtifact.created_at)
    )
    artifacts = list(art_result.scalars().all())

    del_result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.sei_process_id == document.sei_process_id,
            ImportedArtifact.status == ArtifactStatus.DELETED,
        ).order_by(ImportedArtifact.created_at)
    )
    deleted_artifacts = list(del_result.scalars().all())

    # ── Fetch relevant audit logs ─────────────────────────────────────────────
    artifact_ids = [str(a.id) for a in artifacts]
    # Include all artifacts (even deleted) for history — fetch all for this process
    all_art_result = await db.execute(
        select(ImportedArtifact.id).where(
            ImportedArtifact.sei_process_id == document.sei_process_id
        )
    )
    all_artifact_ids = [str(r) for r in all_art_result.scalars().all()]

    log_conditions = []
    if all_artifact_ids:
        log_conditions.append(
            (AuditLog.entity_type == "artifact") & (AuditLog.entity_id.in_(all_artifact_ids))
        )
    log_conditions.append(
        (AuditLog.entity_type == "document") & (AuditLog.entity_id == str(document.id))
    )

    from sqlalchemy import or_
    log_result = await db.execute(
        select(AuditLog)
        .where(or_(*log_conditions))
        .order_by(AuditLog.created_at)
    )
    audit_logs = list(log_result.scalars().all())

    # ── Load user names ───────────────────────────────────────────────────────
    user_ids = (
        {str(a.user_id) for a in artifacts}
        | {str(a.user_id) for a in deleted_artifacts}
        | {str(l.user_id) for l in audit_logs if l.user_id}
    )
    users_by_id = await _load_users_by_id(db, user_ids)

    rebuilt_at = datetime.utcnow()
    html = _render_html(process, artifacts, deleted_artifacts, audit_logs, document, users_by_id, rebuilt_at)
    new_hash = _sha256(html)

    if not force and document.last_content_hash == new_hash:
        return document

    # ── Generate PDF ──────────────────────────────────────────────────────────
    docs_dir = os.path.join(settings.UPLOAD_DIR, "documents")
    os.makedirs(docs_dir, exist_ok=True)
    pdf_filename = f"comprovacao_{document.id.hex}.pdf"
    pdf_path = os.path.join(docs_dir, pdf_filename)
    try:
        _generate_pdf(html, pdf_path, process.numero_processo, rebuilt_at)
    except Exception as exc:
        logger.error("PDF generation failed: %s", type(exc).__name__)
        pdf_path = document.pdf_path  # keep previous PDF

    # ── Determine new status ──────────────────────────────────────────────────
    was_sent = document.send_to_sei_status == SendToSEIStatus.SENT
    if was_sent and document.last_content_hash and document.last_content_hash != new_hash:
        new_status = DocumentStatus.NEEDS_REISSUE
    elif document.status == DocumentStatus.DRAFT:
        new_status = DocumentStatus.GENERATED
    else:
        new_status = document.status  # preserve current status

    document.document_html = html
    document.pdf_path = pdf_path
    document.last_content_hash = new_hash
    document.last_rebuilt_at = rebuilt_at
    document.version_number = (document.version_number or 0) + 1
    document.status = new_status
    await db.flush()
    return document


async def generate_document(
    db: AsyncSession,
    sei_process_id: uuid.UUID,
    current_user: User,
) -> ImportDocument:
    """Public entry-point: get-or-create the single comprovante, then rebuild its content."""
    proc_result = await db.execute(select(SEIProcess).where(SEIProcess.id == sei_process_id))
    process = proc_result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")

    art_result = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.sei_process_id == sei_process_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    if not art_result.scalars().all():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum artefato ativo para este processo. Importe ao menos um artefato antes de gerar o comprovante.",
        )

    document, _created = await get_or_create_import_document(db, sei_process_id, current_user)
    document = await rebuild_import_document_content(db, document, force=True)

    # Lock all active artifacts
    art_result2 = await db.execute(
        select(ImportedArtifact).where(
            ImportedArtifact.sei_process_id == sei_process_id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    for artifact in art_result2.scalars().all():
        artifact.document_locked = True
    await db.flush()
    await db.refresh(document)
    return document


def _generate_pdf(html: str, output_path: str, process_number: str, generated_at: datetime) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Heading1"], fontSize=13,
                                  textColor=colors.HexColor("#003366"), alignment=1, spaceAfter=4)
    sub_style = ParagraphStyle("s", parent=styles["Normal"], fontSize=10,
                                textColor=colors.HexColor("#003366"), alignment=1, spaceAfter=10)
    normal_style = ParagraphStyle("n", parent=styles["Normal"], fontSize=9, spaceAfter=6)

    story = [
        Paragraph("Instituto Federal de Educação, Ciência e Tecnologia de Pernambuco — IFPE", title_style),
        Paragraph("Documento de Comprovação de Importação de Artefatos", sub_style),
        Paragraph(f"Processo SEI: {process_number}", sub_style),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#003366")),
        Spacer(1, 10),
        Paragraph(f"Última atualização: {_fmt(generated_at)}", normal_style),
        Spacer(1, 6),
        Paragraph(
            "Para visualização completa com tabelas de artefatos e histórico de auditoria, "
            "utilize a versão HTML disponível no sistema.",
            normal_style,
        ),
        Spacer(1, 6),
        Paragraph(
            "Este documento consolida o registro de importação dos artefatos técnicos oriundos do "
            "Compras.gov.br e o registro de seus hashes SHA-256 para fins de rastreabilidade e integridade, "
            "em conformidade com a Lei nº 14.133/2021.",
            normal_style,
        ),
    ]
    doc.build(story)
