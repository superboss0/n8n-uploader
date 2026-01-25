import os
from telethon import TelegramClient
from telethon.sessions import StringSession

_api_id = int(os.environ["TG_API_ID"])
_api_hash = os.environ["TG_API_HASH"]
_session = os.environ["TG_SESSION"]

client = TelegramClient(StringSession(_session), _api_id, _api_hash)


def _is_intlike(s: str) -> bool:
    s = str(s).strip()
    return s.lstrip("-").isdigit()


async def _resolve_target(target):
    """
    Поддерживает:
      - 'me'
      - '@username'
      - numeric id (если уже известен сессии; иначе прогреваем dialogs и пробуем снова)
      - любой другой string (как есть)
    """
    t = str(target).strip()

    if t == "me":
        return "me"

    if t.startswith("@"):
        return t

    if _is_intlike(t):
        n = int(t)
        try:
            return await client.get_input_entity(n)
        except Exception:
            await client.get_dialogs(limit=200)
            return await client.get_input_entity(n)

    return t


async def send_tg(target: str, text: str):
    await client.start()
    peer = await _resolve_target(target)
    await client.send_message(peer, text)


async def send_file(target: str, file_path: str, caption: str | None = None):
    await client.start()
    peer = await _resolve_target(target)
    await client.send_file(peer, file_path, caption=caption)
