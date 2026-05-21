import json
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from app.database import get_db
from app.models.sei_process import SEIProcess, SEIProcessQuery, QueryStatus
from app.models.artifact import ImportedArtifact, ArtifactStatus
from app.models.document import ImportDocument
from app.models.user import User
from app.core.deps import get_current_user, get_client_ip
from app.schemas.sei_process import SEIQueryRequest, SEIQueryResponse, SEIProcessResponse, SEIProcessListItem
from app.services.sei_service import SEIService
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sei-processes", tags=["Processos SEI"])


@router.post("/query", response_model=SEIQueryResponse, status_code=status.HTTP_201_CREATED)
async def query_process(
    body: SEIQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = get_client_ip(request)

    # Create pending query record
    query_record = SEIProcessQuery(
        user_id=current_user.id,
        numero_processo=body.numero_processo,
        status=QueryStatus.PENDING,
    )
    db.add(query_record)
    await db.flush()

    try:
        sei_service = SEIService(db)
        parsed = await sei_service.consultar_procedimento(body.numero_processo)

        if not parsed.get("id_procedimento"):
            raise ValueError("Processo não encontrado no SEI ou resposta inválida")

        numero_normalizado = parsed.get("numero_processo") or body.numero_processo

        # Get-or-create: reuse existing process record (same UUID) so artifacts stay linked
        existing_result = await db.execute(
            select(SEIProcess)
            .where(SEIProcess.numero_processo == numero_normalizado)
            .order_by(SEIProcess.created_at.desc())
            .limit(1)
        )
        existing_process = existing_result.scalar_one_or_none()

        if existing_process:
            # Update fields in-place, keeping the same UUID and all linked artifacts/documents
            existing_process.query_id = query_record.id
            existing_process.id_procedimento = parsed.get("id_procedimento")
            existing_process.especificacao = parsed.get("especificacao")
            existing_process.data_autuacao = parsed.get("data_autuacao")
            existing_process.link_acesso = parsed.get("link_acesso")
            existing_process.nivel_acesso_local = parsed.get("nivel_acesso_local")
            existing_process.nivel_acesso_global = parsed.get("nivel_acesso_global")
            existing_process.tipo_procedimento_id = parsed.get("tipo_procedimento_id")
            existing_process.tipo_procedimento_nome = parsed.get("tipo_procedimento_nome")
            existing_process.unidade_sigla = parsed.get("unidade_sigla")
            existing_process.unidade_descricao = parsed.get("unidade_descricao")
            existing_process.ultimo_andamento = parsed.get("ultimo_andamento")
            existing_process.raw_response_json = parsed.get("raw_response_json")
            process = existing_process
            logger.info("PROCESS GET (existing)  numero=%s  id=%s", numero_normalizado, process.id)
        else:
            process = SEIProcess(
                query_id=query_record.id,
                id_procedimento=parsed.get("id_procedimento"),
                numero_processo=numero_normalizado,
                especificacao=parsed.get("especificacao"),
                data_autuacao=parsed.get("data_autuacao"),
                link_acesso=parsed.get("link_acesso"),
                nivel_acesso_local=parsed.get("nivel_acesso_local"),
                nivel_acesso_global=parsed.get("nivel_acesso_global"),
                tipo_procedimento_id=parsed.get("tipo_procedimento_id"),
                tipo_procedimento_nome=parsed.get("tipo_procedimento_nome"),
                unidade_sigla=parsed.get("unidade_sigla"),
                unidade_descricao=parsed.get("unidade_descricao"),
                ultimo_andamento=parsed.get("ultimo_andamento"),
                raw_response_json=parsed.get("raw_response_json"),
            )
            db.add(process)
            logger.info("PROCESS CREATE (new)  numero=%s", numero_normalizado)

        query_record.status = QueryStatus.SUCCESS
        query_record.response_summary = json.dumps({
            "id_procedimento": parsed.get("id_procedimento"),
            "numero_processo": parsed.get("numero_processo"),
            "tipo": parsed.get("tipo_procedimento_nome"),
        })

        await db.flush()
        await db.refresh(query_record)
        await db.refresh(process)

        query_record.process = process

        await log_action(
            db,
            action="SEI_PROCESS_QUERIED",
            user_id=current_user.id,
            entity_type="sei_process",
            entity_id=str(process.id),
            ip_address=ip,
            metadata={"numero_processo": body.numero_processo},
        )

    except Exception as e:
        query_record.status = QueryStatus.ERROR
        query_record.error_message = str(e)[:500]
        await db.flush()

        await log_action(
            db,
            action="SEI_QUERY_FAILED",
            user_id=current_user.id,
            entity_type="sei_process_query",
            entity_id=str(query_record.id),
            ip_address=ip,
            metadata={"numero_processo": body.numero_processo, "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao consultar processo no SEI: {str(e)}",
        )

    return query_record


@router.get("/", response_model=list[SEIProcessListItem])
async def list_processes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    result = await db.execute(
        select(SEIProcess)
        .order_by(SEIProcess.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    processes = result.scalars().all()

    items = []
    for p in processes:
        count_result = await db.execute(
            select(func.count(ImportedArtifact.id)).where(
                ImportedArtifact.sei_process_id == p.id,
                ImportedArtifact.status == ArtifactStatus.ACTIVE,
            )
        )
        count = count_result.scalar() or 0
        items.append(SEIProcessListItem(
            id=p.id,
            numero_processo=p.numero_processo,
            especificacao=p.especificacao,
            tipo_procedimento_nome=p.tipo_procedimento_nome,
            unidade_sigla=p.unidade_sigla,
            data_autuacao=p.data_autuacao,
            created_at=p.created_at,
            artifacts_count=count,
        ))
    return items


@router.get("/{process_id}", response_model=SEIProcessResponse)
async def get_process(
    process_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(SEIProcess).where(SEIProcess.id == process_id))
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")

    count_result = await db.execute(
        select(func.count(ImportedArtifact.id)).where(
            ImportedArtifact.sei_process_id == process.id,
            ImportedArtifact.status == ArtifactStatus.ACTIVE,
        )
    )
    artifacts_count = count_result.scalar() or 0

    from app.models.document import ImportDocument
    doc_count_result = await db.execute(
        select(func.count(ImportDocument.id)).where(ImportDocument.sei_process_id == process.id)
    )
    documents_count = doc_count_result.scalar() or 0

    # Parse ultimo_andamento JSON for response
    ultimo = None
    if process.ultimo_andamento:
        try:
            ultimo = json.loads(process.ultimo_andamento)
        except Exception:
            ultimo = None

    return SEIProcessResponse(
        id=process.id,
        query_id=process.query_id,
        id_procedimento=process.id_procedimento,
        numero_processo=process.numero_processo,
        especificacao=process.especificacao,
        data_autuacao=process.data_autuacao,
        link_acesso=process.link_acesso,
        nivel_acesso_local=process.nivel_acesso_local,
        nivel_acesso_global=process.nivel_acesso_global,
        tipo_procedimento_id=process.tipo_procedimento_id,
        tipo_procedimento_nome=process.tipo_procedimento_nome,
        unidade_sigla=process.unidade_sigla,
        unidade_descricao=process.unidade_descricao,
        ultimo_andamento=ultimo,
        created_at=process.created_at,
        artifacts_count=artifacts_count,
        documents_count=documents_count,
    )


@router.delete("/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process(
    process_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a SEI process and all associated data in cascade:
    import documents → artifacts (+ physical files) → process → query record.
    Audit logs are retained (they reference entity_id as strings, not FK).
    """
    result = await db.execute(select(SEIProcess).where(SEIProcess.id == process_id))
    process = result.scalar_one_or_none()
    if not process:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")

    await log_action(
        db,
        action="SEI_PROCESS_DELETED",
        user_id=current_user.id,
        entity_type="sei_process",
        entity_id=str(process_id),
        ip_address=get_client_ip(request),
        metadata={
            "numero_processo": process.numero_processo,
            "id_procedimento": process.id_procedimento,
        },
    )

    # 1. Delete import documents
    doc_result = await db.execute(
        select(ImportDocument).where(ImportDocument.sei_process_id == process_id)
    )
    for doc in doc_result.scalars().all():
        await db.delete(doc)

    # 2. Delete artifacts and their physical files
    art_result = await db.execute(
        select(ImportedArtifact).where(ImportedArtifact.sei_process_id == process_id)
    )
    for art in art_result.scalars().all():
        if art.storage_path:
            try:
                os.remove(art.storage_path)
            except OSError:
                logger.warning("Could not remove artifact file: %s", art.storage_path)
        await db.delete(art)

    # 3. Delete the process (must flush before deleting query due to FK)
    query_id = process.query_id
    await db.delete(process)
    await db.flush()

    # 4. Delete the associated query record
    query_result = await db.execute(
        select(SEIProcessQuery).where(SEIProcessQuery.id == query_id)
    )
    query_rec = query_result.scalar_one_or_none()
    if query_rec:
        await db.delete(query_rec)
