import os
import re
from telethon import events
from tg_sender import client  # используем тот же Telethon client и сессию

# Куда пересылать алерты
ALERT_TARGET = os.environ.get("ALERT_TARGET", "4906022006")

# TRC-20 (TRON) адрес
TRC20_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")

# Запрос кошелька (RU)
REQ_PATTERNS = [
    r"\b(пришлите|скиньте|киньте|дайте|подскажите|предоставьте|нужен)\b.*\bкошел[её]к\b",
    r"\b(актуальный|на сегодня|сегодняшний)\b.*\bкошел[её]к\b",
    r"\b(на какой|куда)\b.*\bкошел[её]к\b",
    r"\bкошел[её]к\b.*\b(на сегодня|актуальный|для пополнения|для при[её]ма|принять)\b",
]

REQ_RE = re.compile("|".join(f"(?:{p})" for p in REQ_PATTERNS), re.IGNORECASE)

# Исключения (не запрос)
NEG_RE = re.compile(
    r"(кошел[её]к тот же|тот же кошел[её]к|"
    r"был приход|поступлен|не вижу поступлен|"
    r"сменить кошел[её]к|заменить кошел[её]к|друг(ой|ого) кошел[её]к|чистый|"
    r"кошел[её]ка нет|нет кошел[её]ка|не имею кошел[её]ка|"
    r"кошел[её]ки для вывода)",
    re.IGNORECASE
)

def is_wallet_request_ru_trc20(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False

    # если уже есть адрес — это не запрос
    if TRC20_RE.search(t):
        return False

    # исключения
    if NEG_RE.search(t):
        return False

    # запрос
    return bool(REQ_RE.search(t))


def install_handlers():
    """
    Вешаем обработчик на общий Telethon client.
    Вызывается один раз при старте приложения.
    """

    @client.on(events.NewMessage)
    async def handler(event):
        text = event.raw_text or ""
        if not is_wallet_request_ru_trc20(text):
            return

        sender = await event.get_sender()
        chat = await event.get_chat()

        sender_name = (
            getattr(sender, "username", None)
            or getattr(sender, "first_name", "")
            or "unknown"
        )
        chat_name = (
            getattr(chat, "title", None)
            or getattr(chat, "username", None)
            or "private"
        )

        alert = (
            f"💼 *Запрос актуального кошелька (TRC-20)*\n"
            f"👤 From: `{sender_name}`\n"
            f"💬 Source: `{chat_name}`\n\n"
            f"{text}"
        )

        target = ALERT_TARGET
        if str(target).lstrip("-").isdigit():
            target = int(target)

        await client.send_message(target, alert, parse_mode="md")
