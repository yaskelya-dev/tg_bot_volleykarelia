from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    API_SECRET_KEY: str
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DB_PATH: str = "bot_data.db"

    class Config:
        env_file = ".env"

settings = Settings()
