from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.sei_config import SEIConfig
from app.models.user import User
from app.core.deps import require_admin, get_client_ip
from app.core.crypto import encrypt_value
from app.schemas.sei_config import (
    SEIConfigCreate, SEIConfigUpdate, SEIConfigResponse, SEIWriteStatusResponse,
)
from app.services.audit_service import log_action
from app.services.sei_service import SEIService
from app.config import settings

router = APIRouter(prefix="/sei-config", tags=["Configuração SEI"])


@router.get("/", response_model=SEIConfigResponse | None)
async def get_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(SEIConfig).where(SEIConfig.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/", response_model=SEIConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    body: SEIConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = await db.execute(select(SEIConfig).where(SEIConfig.is_active == True))
    for old in existing.scalars().all():
        old.is_active = False

    config = SEIConfig(
        soap_url=body.soap_url,
        sigla_sistema=body.sigla_sistema,
        identificacao_servico_encrypted=encrypt_value(body.identificacao_servico),
        id_unidade_default=body.id_unidade_default,
        sin_retornar_assuntos=body.sin_retornar_assuntos,
        sin_retornar_interessados=body.sin_retornar_interessados,
        sin_retornar_observacoes=body.sin_retornar_observacoes,
        sin_retornar_ultimo_andamento=body.sin_retornar_ultimo_andamento,
        sin_retornar_unidades=body.sin_retornar_unidades,
        enable_write_operations=body.enable_write_operations,
        external_document_series_id=body.external_document_series_id or None,
        confirmation_document_series_id=body.confirmation_document_series_id or None,
        tipo_conferencia_id=body.tipo_conferencia_id or None,
    )
    db.add(config)
    await db.flush()

    await log_action(
        db,
        action="SEI_CONFIG_CREATED",
        user_id=admin.id,
        entity_type="sei_config",
        entity_id=str(config.id),
        ip_address=get_client_ip(request),
        metadata={
            "soap_url": config.soap_url,
            "sigla_sistema": config.sigla_sistema,
            "enable_write_operations": config.enable_write_operations,
        },
    )
    await db.refresh(config)
    return config


@router.put("/", response_model=SEIConfigResponse)
async def update_config(
    body: SEIConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(SEIConfig).where(SEIConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuração não encontrada")

    config.soap_url = body.soap_url
    config.sigla_sistema = body.sigla_sistema
    config.id_unidade_default = body.id_unidade_default
    config.sin_retornar_assuntos = body.sin_retornar_assuntos
    config.sin_retornar_interessados = body.sin_retornar_interessados
    config.sin_retornar_observacoes = body.sin_retornar_observacoes
    config.sin_retornar_ultimo_andamento = body.sin_retornar_ultimo_andamento
    config.sin_retornar_unidades = body.sin_retornar_unidades
    config.enable_write_operations = body.enable_write_operations
    config.external_document_series_id = body.external_document_series_id or None
    config.confirmation_document_series_id = body.confirmation_document_series_id or None
    config.tipo_conferencia_id = body.tipo_conferencia_id or None

    if body.identificacao_servico:
        config.identificacao_servico_encrypted = encrypt_value(body.identificacao_servico)

    await db.flush()
    await log_action(
        db,
        action="SEI_CONFIG_UPDATED",
        user_id=admin.id,
        entity_type="sei_config",
        entity_id=str(config.id),
        ip_address=get_client_ip(request),
        metadata={
            "soap_url": config.soap_url,
            "enable_write_operations": config.enable_write_operations,
        },
    )
    await db.refresh(config)
    return config


@router.get("/status")
async def check_sei_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(SEIConfig).where(SEIConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()

    if config:
        return {"configured": True, "source": "database", "soap_url": config.soap_url}
    if settings.SEI_SOAP_URL and settings.SEI_IDENTIFICACAO_SERVICO:
        return {"configured": True, "source": "environment", "soap_url": settings.SEI_SOAP_URL}
    return {"configured": False, "source": None}


@router.get("/write-status", response_model=SEIWriteStatusResponse)
async def get_write_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Returns whether write operations are enabled and what configuration is present."""
    result = await db.execute(select(SEIConfig).where(SEIConfig.is_active == True).limit(1))
    config = result.scalar_one_or_none()

    write_enabled = settings.SEI_ENABLE_WRITE_OPERATIONS or (
        config.enable_write_operations if config else False
    )
    if settings.SEI_ENABLE_WRITE_OPERATIONS:
        source = "env"
    elif config and config.enable_write_operations:
        source = "db_config"
    else:
        source = "disabled"

    ext_series = bool(
        (config.external_document_series_id if config else None)
        or settings.SEI_DEFAULT_EXTERNAL_DOCUMENT_SERIES_ID
    )
    conf_series = bool(
        (config.confirmation_document_series_id if config else None)
        or settings.SEI_DEFAULT_CONFIRMATION_DOCUMENT_SERIES_ID
    )

    return SEIWriteStatusResponse(
        write_enabled=write_enabled,
        source=source,
        external_series_configured=ext_series,
        confirmation_series_configured=conf_series,
    )


@router.get("/series")
async def list_series(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Query SEI for all document series available in the configured unit.
    Used by admins to discover the correct IdSerie value.
    """
    try:
        service = SEIService(db=db)
        series = await service.listar_series()
        return series
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao consultar séries no SEI: {str(exc)}",
        )
