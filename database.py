import aiosqlite
from datetime import datetime
from config import settings


async def init_db():
    async with aiosqlite.connect(settings.DB_PATH) as db:
        # Таблица пользователей для маппинга @username -> chat_id
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL
            )
        """)
        # Таблица кодов подтверждения
        await db.execute("""
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at DATETIME NOT NULL,
                is_used BOOLEAN DEFAULT 0
            )
        """)
        await db.commit()


async def register_user(chat_id: int, username: str):
    if not username:
        return
    username = username.lower().replace("@", "")
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (chat_id, username) 
            VALUES (?, ?) 
            ON CONFLICT(chat_id) DO UPDATE SET username = excluded.username
        """, (chat_id, username))
        await db.commit()


async def get_chat_id_by_username(username: str) -> int | None:
    username = username.lower().replace("@", "")
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT chat_id FROM users WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def save_code(username: str, code: str, expires_at: datetime):
    username = username.lower().replace("@", "")
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            INSERT INTO verification_codes (username, code, expires_at)
            VALUES (?, ?, ?)
        """, (username, code, expires_at))
        await db.commit()
