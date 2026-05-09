import asyncio
import logging

import asyncpg
from asyncpg.exceptions import InterfaceError
from contextlib import asynccontextmanager
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self, max_retries: int = 5, base_delay: float = 1.0):
        """Connect to PostgreSQL with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                self.pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=settings.db_pool_min_size,
                    max_size=settings.db_pool_max_size,
                    command_timeout=settings.db_command_timeout,
                    server_settings={"jit": "off"},
                )
                # Test connection
                async with self.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                logging.info("Database connected successfully")
                return
            except Exception as e:
                delay = min(base_delay * (2 ** attempt), 30)  # cap at 30s
                logging.warning(
                    f"DB connection attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
        raise ConnectionError(
            f"Failed to connect to database after {max_retries} attempts"
        )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def health_check(self) -> bool:
        """Quick health check — returns True if DB is reachable."""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    async def reconnect(self):
        """Disconnect and reconnect to DB."""
        await self.disconnect()
        await self.connect()

    @asynccontextmanager
    async def transaction(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def fetch(self, query, *args):
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)
        except InterfaceError:
            logging.warning("DB connection lost during fetch, attempting reconnect...")
            await self.reconnect()
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        except InterfaceError:
            logging.warning("DB connection lost during fetchrow, attempting reconnect...")
            await self.reconnect()
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(query, *args)

    async def execute(self, query, *args):
        try:
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)
        except InterfaceError:
            logging.warning("DB connection lost during execute, attempting reconnect...")
            await self.reconnect()
            async with self.pool.acquire() as conn:
                return await conn.execute(query, *args)


db = Database()
