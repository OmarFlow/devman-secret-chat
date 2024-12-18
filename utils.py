from contextlib import asynccontextmanager


@asynccontextmanager
async def connection_manager(connection):
    try:
        yield connection
    finally:
        _, writer = connection
        writer.close()
        await writer.wait_closed()
