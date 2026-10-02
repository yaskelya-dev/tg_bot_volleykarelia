import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, status, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

from config import settings
import database as db

# Инициализация бота и FastAPI
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# Проверка безопасности REST API
async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный API-ключ безопасности"
        )
    return api_key


# Схема входящего запроса от сайта
class SendCodeRequest(BaseModel):
    username: str = Field(..., description="Telegram username пользователя")
    code: str = Field(..., min_length=6, max_length=6, description="6-значный код")
    expires_at: datetime = Field(..., description="Дата и время истечения (ISO format)")


# Хэндлеры Telegram бота
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not message.from_user.username:
        await message.answer(
            "У вас не установлен Username в Telegram. "
            "Установите его в настройках профиля, чтобы получать коды подтверждения."
        )
        return

    await db.register_user(message.chat.id, message.from_user.username)
    await message.answer("Вы успешно зарегистрированы! Теперь вы можете получать коды подтверждения.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация БД
    await db.init_db()

    # Запуск polling бота в фоновом режиме
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    # Остановка при завершении
    polling_task.cancel()
    await bot.session.close()
    await db.engine.dispose()  # Закрываем соединения к БД


app = FastAPI(title="TG Code Verification Service", lifespan=lifespan)


# Эндпоинт для отправки кода с сайта
@app.post("/api/v1/send-code", dependencies=[Depends(verify_api_key)])
async def send_code(req: SendCodeRequest):
    chat_id = await db.get_chat_id_by_username(req.username)

    if not chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь @{req.username} не найден. Он должен сначала запустить бота в Telegram."
        )

    # Форматируем время окончания действия
    expire_str = req.expires_at.strftime("%H:%M:%S %d.%m.%Y")
    text = (
        f"**Ваш код подтверждения:** `{req.code}`\n\n"
        f"Код действителен до: **{expire_str}**\n"
        f"Никому не передавайте этот код!"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        await db.save_code(req.username, req.code, req.expires_at)
        return {"status": "success", "message": "Код успешно отправлен"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось отправить сообщение: {str(e)}"
        )
