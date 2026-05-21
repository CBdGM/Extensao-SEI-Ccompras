import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from app.core.deps import get_current_user, get_client_ip
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from app.schemas.user import UserResponse
from app.services.audit_service import log_action
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent", "")

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Use constant-time comparison to prevent timing attacks
    valid = user and user.is_active and verify_password(body.password, user.password_hash)

    if not valid:
        logger.warning("LOGIN FALHOU  email=%s  ip=%s", body.email, ip)
        await log_action(
            db,
            action="LOGIN_FAILED",
            entity_type="auth",
            ip_address=ip,
            user_agent=ua,
            metadata={"email": body.email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id), user.role.value)

    logger.info("LOGIN OK  user=%s  role=%s  ip=%s", user.email, user.role.value, ip)
    await log_action(
        db,
        action="LOGIN_SUCCESS",
        user_id=user.id,
        entity_type="auth",
        ip_address=ip,
        user_agent=ua,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = verify_refresh_token(body.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token_new = create_refresh_token(str(user.id), user.role.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await log_action(
        db,
        action="LOGOUT",
        user_id=current_user.id,
        entity_type="auth",
        ip_address=get_client_ip(request),
    )
    return {"message": "Logout realizado com sucesso"}
