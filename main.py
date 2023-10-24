import asyncio
from datetime import datetime

import aiofiles


async def chat_spy():
    reader, writer = await asyncio.open_connection(
        'minechat.dvmn.org', 5000)
    try:
        while not reader.at_eof():
            data = await reader.read(500)
            async with aiofiles.open('chat_log.txt', mode='a') as f:
                write_str = f'{datetime.now().strftime("[%d.%m.%y %H:%M]")} {data.decode(errors="ignore")}'
                await f.write(write_str)
            print(f'Received: {data.decode(errors="ignore")!r}')
    except ConnectionError:
        print("Network error")


asyncio.run(chat_spy())