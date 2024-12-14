import argparse
import asyncio
import json
import time
from asyncio.streams import StreamWriter, StreamReader
import logging
from typing import Optional

from tkinter import messagebox
from anyio import create_task_group

import gui
from utils import connection_closing
from exceptions import InvalidTokenException


messages_queue = asyncio.Queue()
sending_queue = asyncio.Queue()
log_queue = asyncio.Queue()
status_updates_queue = asyncio.Queue()
watchdog_queue = asyncio.Queue()


chat_logger = logging.getLogger('chat')
chat_logger.setLevel(logging.INFO)
fh = logging.FileHandler('sending.log', encoding='utf-8')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(message)s')
fh.setFormatter(formatter)
chat_logger.addHandler(fh)


watch_logger = logging.getLogger('watch')
watch_logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
watch_logger.addHandler(ch)


async def write_log(log_queue: asyncio.Queue) -> None:
    while True:
        msg = await log_queue.get()
        chat_logger.info(msg)


async def watch_for_connection(watchdog_queue: asyncio.Queue) -> None:
    while True:
        msg = await watchdog_queue.get()
        watch_logger.debug(msg)


async def authorise(writer: StreamWriter, reader: StreamReader,
                    key: Optional[str], user_name: Optional[str], log_queue: asyncio.Queue) -> bool:
    if key:
        writer.write(f"{key}\n\n".encode())
        await writer.drain()
        response = await reader.read(2000)
        response = response.decode()
        if 'null' in response:
            invalid_token_message = "Неизвестный токен. Проверьте его или зарегистрируйте заново."
            messagebox.showinfo("Не верный токен", invalid_token_message)
            log_queue.put_nowait(invalid_token_message)
            raise InvalidTokenException
        name = json.loads(response.split("\n")[0])['nickname']
        event = gui.NicknameReceived(name)
        status_updates_queue.put_nowait(event)
        return True


async def submit_message(writer, message, log_queue: asyncio.Queue):
    writer.write(f"{message}\n\n".encode())
    await writer.drain()
    log_queue.put_nowait("Ваше сообщение отправлено")


async def chat_spy(host: str, port: int, chat_queue: asyncio.Queue,
                   log_queue: asyncio.Queue, watchdog_queue: asyncio.Queue):

    status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)

    async with connection_closing(await asyncio.open_connection(host, port)) as conn:
        reader, _ = conn
        status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)
        while not reader.at_eof():
            try:
                 async with asyncio.timeout(1):
                    data = await reader.read(500)
                    msg = data.decode(errors="ignore")
                    log_queue.put_nowait(msg)
                    chat_queue.put_nowait(msg)
                    watchdog_queue.put_nowait(f'[{time.time()}] Connection is Alive. New message in chat')
            except asyncio.TimeoutError:
                write_str = f'[{time.time()}] 1s timeout is elapsed'
                watchdog_queue.put_nowait(write_str)


async def chat_say(host: str, port: int, chat_key: Optional[str],
                   user_name: Optional[str], watchdog_queue: asyncio.Queue, log_queue: asyncio.Queue):

    status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)

    async with connection_closing(await asyncio.open_connection(host, port)) as conn:
        reader, writer = conn
        status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)

        await reader.readuntil()

        await authorise(writer, reader, chat_key, user_name, log_queue)
        watchdog_queue.put_nowait(f'[{time.time()}] Connection is Alive. Authorization done')

        while True:
            message = await sending_queue.get()
            await submit_message(writer, f"{message!r}", log_queue)
            watchdog_queue.put_nowait(f'[{time.time()}] Connection is Alive. Message sent')


async def ping_pong(host: str, port: int):
    reader , writer = await asyncio.open_connection(host, port)
    while True:
        message = ''
        writer.write(f"{message}\n\n".encode())
        await writer.drain()

        try:
            async with asyncio.timeout(1):
                data = await reader.read(500)
                if data == b'\n':
                    raise ConnectionError
        except asyncio.TimeoutError:
            raise ConnectionError
        await asyncio.sleep(0.3)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="specify the host", type=str)
    parser.add_argument("read_port", help="specify the port for reading messages", type=int)
    parser.add_argument("write_port", help="specify the port for sending messages", type=int)
    parser.add_argument("history", help="path to log file", type=str)
    parser.add_argument("--key", help="personal chat key", type=str)
    parser.add_argument("--user_name", help="specify user name", type=str)
    args = parser.parse_args()

    async def handle_connection():
        while True:
            try:
                async with create_task_group() as tg:
                    tg.start_soon(chat_spy, args.host, args.read_port, messages_queue, log_queue, watchdog_queue)
                    tg.start_soon(watch_for_connection, watchdog_queue)
                    tg.start_soon(chat_say, args.host, args.write_port, args.key, args.user_name, watchdog_queue, log_queue)
                    tg.start_soon(ping_pong, args.host, args.write_port)
            except* ConnectionError as excgroup:
                log_queue.put_nowait("Network Error")
                status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.CLOSED)

    async def main():
        async with create_task_group() as tg:
            tg.start_soon(gui.draw, messages_queue, sending_queue, status_updates_queue)
            tg.start_soon(write_log, log_queue)
            tg.start_soon(handle_connection)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, gui.TkAppClosed):
        print("App was cloased")
