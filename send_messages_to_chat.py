import argparse
import asyncio
import logging
from anyio import create_task_group
import aiofiles

from utils import connection_manager

logging.basicConfig(filename='sending.log', encoding='utf-8', level=logging.DEBUG, datefmt='%d.%m.%y %H:%M', format='%(asctime)s %(message)s')


async def write_info_log(msg):
    print(msg)
    logging.info(msg)


async def register(writer, reader, user_name):
    writer.write("\n".encode())
    writer.write(f"{user_name!r}\n\n".encode())
    await writer.drain()

    await reader.readuntil()
    cred = await reader.readuntil()

    async with aiofiles.open('credentails.txt', mode='wb') as f:
        await f.write(cred)

    await write_info_log("Вы успешно зарегистрировались, ваши данные находятся в файле credentails.txt")


async def submit_message(writer, message):
    if message is None:
        message = ''
    writer.write(f"{message}\n\n".encode())
    await writer.drain()
    await write_info_log("Ваше сообщение отправлено")


async def authorise(writer, reader, key, user_name):
    if key:
        writer.write(f"{key}\n\n".encode())
        await writer.drain()
        response = await reader.read(2000)
        if 'null' in response.decode():
            await write_info_log("Неизвестный токен. Проверьте его или зарегистрируйте заново.")
            return None
        return True
    else:
        await register(writer, reader, user_name)
        return True


async def chat_say(host, port, message, chat_key=None, user_name=None):
    try:
        async with connection_manager(await asyncio.open_connection(host, port)) as conn:
            reader, writer = conn
            hello_message = await reader.readuntil()
            logging.debug(hello_message.decode())

            auth = await authorise(writer, reader, chat_key, user_name)
            if auth is not None:
                await submit_message(writer, f"{message!r}")
    except ConnectionError:
        await write_info_log("Network error")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="specify the host", type=str)
    parser.add_argument("port", help="specify the port", type=int)
    parser.add_argument("--msg", help="message to send", type=str)
    parser.add_argument("--key", help="personal chat key", type=str)
    parser.add_argument("--user_name", help="specify user name", type=str)
    args = parser.parse_args()

    asyncio.run(chat_say(args.host, args.port, args.msg, args.key, args.user_name))
