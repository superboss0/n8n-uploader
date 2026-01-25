import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

_api_id = int(os.environ["TG_API_ID"])
_api_hash = os.environ["TG_API_HASH"]
_session = os.environ["TG_SESSION"]

client = TelegramClient(
    StringSession(_session),
    _api_id,
    _api_hash,
)

async def send_tg(target: str, text: str):
    await client.start()
    await client.send_message(target, text)
