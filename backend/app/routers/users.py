from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password
from app.core.deps import get_current_user, require_admin, get_client_ip
from app.schemas.user import UserCreate, UserUpdate, UserResponse, ChangePasswordRequest, AdminResetPasswordRequest
from app.services.audit_service import log_action

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("/", response_model=list[UserResponse], dependencies=[Depends(require_admin)])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    await log_action(
        db,
        action="USER_CREATED",
        user_id=current_admin.id,
        entity_type="user",
        entity_id=str(user.id),
        ip_address=get_client_ip(request),
        metadata={"email": user.email, "role": user.role.value},
    )
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Users can only view themselves unless admin
    from app.models.user import UserRole
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if body.name is not None:
        user.name = body.name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        user.role = body.role

    await db.flush()
    await log_action(
        db,
        action="USER_UPDATED",
        user_id=current_admin.id,
        entity_type="user",
        entity_id=str(user_id),
        ip_address=get_client_ip(request),
    )
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: UUID,
    body: AdminResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Admin resets another user's password without needing the current password."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    user.password_hash = hash_password(body.new_password)
    await db.flush()
    await log_action(
        db,
        action="PASSWORD_RESET_BY_ADMIN",
        user_id=current_admin.id,
        entity_type="user",
        entity_id=str(user_id),
        ip_address=get_client_ip(request),
        metadata={"target_email": user.email, "admin_email": current_admin.email},
    )
    return {"message": "Senha redefinida com sucesso"}


@router.post("/me/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta")

    current_user.password_hash = hash_password(body.new_password)
    await db.flush()
    await log_action(
        db,
        action="PASSWORD_CHANGED",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(current_user.id),
        ip_address=get_client_ip(request),
    )
    return {"message": "Senha alterada com sucesso"}
