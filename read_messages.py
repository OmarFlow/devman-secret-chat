import argparse
import asyncio
from datetime import datetime

import aiofiles


async def chat_spy(host, port, log_file):
    reader, writer = await asyncio.open_connection(
        host, port)
    try:
        while not reader.at_eof():
            data = await reader.read(500)
            async with aiofiles.open(log_file, mode='a') as f:
                write_str = f'{datetime.now().strftime("[%d.%m.%y %H:%M]")} {data.decode(errors="ignore")}'
                await f.write(write_str)
            print(f'Received: {data.decode(errors="ignore")!r}')
    except ConnectionError:
        print("Network error")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="specify the host", type=str)
    parser.add_argument("port", help="specify the port", type=int)
    parser.add_argument("history", help="path to log file", type=str)
    args = parser.parse_args()

    asyncio.run(chat_spy(args.host, args.port, args.history))