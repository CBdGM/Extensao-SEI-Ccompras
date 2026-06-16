from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from uuid import UUID
from app.models.user import UserRole
import re


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.USER

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Nome deve ter ao menos 2 caracteres")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter ao menos 8 caracteres")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter ao menos uma letra maiúscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter ao menos uma letra minúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter ao menos um número")
        return v


class UserUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


def _validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Senha deve ter ao menos 8 caracteres")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Senha deve conter ao menos uma letra maiúscula")
    if not re.search(r"[a-z]", v):
        raise ValueError("Senha deve conter ao menos uma letra minúscula")
    if not re.search(r"\d", v):
        raise ValueError("Senha deve conter ao menos um número")
    return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class AdminResetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
