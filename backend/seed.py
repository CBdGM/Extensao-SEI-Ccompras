"""
Seed script — creates initial admin and demo user.
Run: docker exec -it compras_sei_backend python seed.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.config import settings
from app.models.user import User, UserRole
from app.core.security import hash_password


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Admin user
        result = await session.execute(select(User).where(User.email == "admin@ifpe.edu.br"))
        if not result.scalar_one_or_none():
            admin = User(
                name="Administrador IFPE",
                email="admin@ifpe.edu.br",
                password_hash=hash_password("Admin@123456"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            print("✓ Admin criado: admin@ifpe.edu.br / Admin@123456")
        else:
            print("→ Admin já existe")

        # Demo user
        result = await session.execute(select(User).where(User.email == "usuario@ifpe.edu.br"))
        if not result.scalar_one_or_none():
            user = User(
                name="Usuário Demonstração",
                email="usuario@ifpe.edu.br",
                password_hash=hash_password("User@123456"),
                role=UserRole.USER,
                is_active=True,
            )
            session.add(user)
            print("✓ Usuário criado: usuario@ifpe.edu.br / User@123456")
        else:
            print("→ Usuário demo já existe")

        await session.commit()
        print("\n✓ Seed concluído com sucesso!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
