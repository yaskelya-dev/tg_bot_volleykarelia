from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, event
from config import settings
from models import Base, User, VerificationCode

DATABASE_URL = f"sqlite+aiosqlite:///{settings.DB_PATH}"

# Создаем асинхронный движок
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30.0}
)

# Фабрика сессий
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Включаем WAL-режим и поддержу Foreign Keys в SQLite
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


async def init_db():
    """Инициализация таблиц при старте приложения"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _clean_username(username: str) -> str:
    """Вспомогательная функция очистки username"""
    return username.lower().replace("@", "").strip()


async def register_user(chat_id: int, username: str) -> None:
    if not username:
        return

    clean_name = _clean_username(username)

    async with async_session() as session:
        async with session.begin():
            # Освобождаем username, если он был закреплен за другим chat_id
            existing_user_with_name = (
                await session.execute(select(User).where(User.username == clean_name))
            ).scalar_one_or_none()

            if existing_user_with_name and existing_user_with_name.chat_id != chat_id:
                existing_user_with_name.username = f"old_{existing_user_with_name.chat_id}"

            # Проверяем самого пользователя
            user = await session.get(User, chat_id)
            if user:
                user.username = clean_name
            else:
                session.add(User(chat_id=chat_id, username=clean_name))


async def get_chat_id_by_username(username: str) -> Optional[int]:
    clean_name = _clean_username(username)
    async with async_session() as session:
        stmt = select(User.chat_id).where(User.username == clean_name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def save_code(username: str, code: str, expires_at: datetime) -> None:
    clean_name = _clean_username(username)
    async with async_session() as session:
        async with session.begin():
            chat_id = (
                await session.execute(select(User.chat_id).where(User.username == clean_name))
            ).scalar_one_or_none()

            if not chat_id:
                raise ValueError(f"Пользователь @{username} не зарегистрирован в системе")

            new_code = VerificationCode(
                chat_id=chat_id,
                code=code,
                expires_at=expires_at
            )
            session.add(new_code)
