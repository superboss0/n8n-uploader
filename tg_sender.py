import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import PeerUser, PeerChat, PeerChannel

_api_id = int(os.environ["TG_API_ID"])
_api_hash = os.environ["TG_API_HASH"]
_session = os.environ["TG_SESSION"]

client = TelegramClient(StringSession(_session), _api_id, _api_hash)

def _to_peer(target: str):
    t = str(target).strip()
    if t == "me":
        return "me"
    if t.startswith("@"):
        return t
    # если число — трактуем как ID (user/chat/channel)
    if t.lstrip("-").isdigit():
        n = int(t)
        # канал обычно -100..., группа может быть отрицательной
        if n < 0 and str(n).startswith("-100"):
            return PeerChannel(int(str(n)[4:]))  # -100123 -> 123
        if n < 0:
            return PeerChat(-n)                 # -123 -> chat_id 123
        return PeerUser(n)                      # 123 -> user_id 123
    return t

async def send_tg(target: str, text: str):
    await client.start()
    peer = await _resolve_target(target)
    await client.send_message(peer, text)

async def send_file(target: str, file_path: str, caption: str | None = None):
    await client.start()
    peer = await _resolve_target(target)
    await client.send_file(peer, file_path, caption=caption)
