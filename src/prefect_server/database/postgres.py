from contextlib import asynccontextmanager

import asyncpg

from prefect_server import config

POOL = None


@asynccontextmanager
async def get_pool_connection():
    """
    Returns a Postgres connection pool.

    Example:
    ```
    async with get_pool_connection() as connection:
        async with connection.transaction():
            await connection.execute(...)
    ```
    """
    global POOL
    if POOL is None:
        POOL = await asyncpg.create_pool(config.database.connection_url)
    async with POOL.acquire() as connection:
        yield connection
