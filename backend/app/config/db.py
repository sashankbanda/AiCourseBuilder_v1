import asyncpg
import os
from typing import Optional

class Database:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                raise ValueError("DATABASE_URL is not set")
            cls._pool = await asyncpg.create_pool(dsn)
            print("[Database] Connection pool created")
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            print("[Database] Connection pool closed")

    @classmethod
    async def fetch(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    @classmethod
    async def execute(cls, query: str, *args):
        pool = await cls.get_pool()
        async with pool.acquire() as connection:
            return await connection.execute(query, *args)
