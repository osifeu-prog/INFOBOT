import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    ADMIN_ID: int
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"
    FULL_SHOP_PRICE: float = 2490.0
    SINGLE_CARD_PRICE: float = 39.0

    class Config:
        env_file = ".env"

settings = Settings()
