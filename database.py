from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    # ייבוא ה-models ואז יצירת הטבלאות
    import models
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
