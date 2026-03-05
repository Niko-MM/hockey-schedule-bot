from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text


DB_URL = "sqlite+aiosqlite:///rhl_zapad.db"


engine = create_async_engine(
    DB_URL,
    echo=False,
    # Ждём до 30 секунд, если файл БД занят
    connect_args={"timeout": 30},
)


async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Включаем WAL-режим для более устойчивой работы с несколькими запросами
        await conn.execute(text("PRAGMA journal_mode=WAL"))
