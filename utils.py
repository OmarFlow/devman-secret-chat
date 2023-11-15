from contextlib import asynccontextmanager


@asynccontextmanager
async def connection_closing(connection):
    try:
        yield connection
    finally:
        _, writer = connection
        writer.close()
        await writer.wait_closed()