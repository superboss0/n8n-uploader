import os
import re
from telethon import events
from telethon.tl.types import User, Channel
from tg_sender import client  # используем тот же Telethon client и сессию

# Куда пересылать алерты
ALERT_TARGET = os.environ.get("ALERT_TARGET", "4906022006")

# TRC-20 (TRON) адрес
TRC20_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")

# Tronscan tx link
TRONSCAN_TX_RE = re.compile(
    r"https?://(?:www\.)?tronscan\.org/#/transaction/[0-9a-fA-F]{16,}",
    re.IGNORECASE
)

# Запрос кошелька (RU) — "пришлите/дайте/актуальный..."
REQ_PATTERNS = [
    r"\b(пришлите|скиньте|киньте|дайте|подскажите|предоставьте|нужен)\b.*\bкошел[её]к\b",
    r"\b(актуальный|на сегодня|сегодняшний)\b.*\bкошел[её]к\b",
    r"\b(на какой|куда)\b.*\bкошел[её]к\b",
    r"\bкошел[её]к\b.*\b(на сегодня|актуальный|для пополнения|для при[её]ма|принять)\b",
]
REQ_RE = re.compile("|".join(f"(?:{p})" for p in REQ_PATTERNS), re.IGNORECASE)

# Запрос подтверждения актуальности кошелька (адрес может быть в тексте)
CONFIRM_PATTERNS = [
    r"\b(подтвердите|подтверди|проверьте|проверь)\b.*\b(актуальност[ьи]|актуален|валидност[ьи]|валиден)\b.*\bкошел[её]к\b",
    r"\bподтвердите\b.*\bкошел[её]к\b",
    r"\bактуальност[ьи]\b.*\bкошел[её]к\b",
    r"\bкошел[её]к\b.*\b(актуален|валиден)\b",
]
CONFIRM_RE = re.compile("|".join(f"(?:{p})" for p in CONFIRM_PATTERNS), re.IGNORECASE)

# "Примите средства / пополнение" + tronscan tx
FUNDS_INBOUND_RE = re.compile(
    r"\b(примите|зачислите|пополнени[ея]|пополним|пополнили|отправили|"
    r"отправили средства|средства для пополнения|на пополнение)\b",
    re.IGNORECASE
)

# Исключения (не запрос кошелька)
NEG_RE = re.compile(
    r"(кошел[её]к тот же|тот же кошел[её]к|"
    r"был приход|поступлен|не вижу поступлен|"
    r"сменить кошел[её]к|заменить кошел[её]к|друг(ой|ого) кошел[её]к|чистый|"
    r"кошел[её]ка нет|нет кошел[её]ка|не имею кошел[её]ка|"
    r"кошел[её]ки для вывода)",
    re.IGNORECASE
)

def is_wallet_confirm_request_ru(text: str) -> bool:
    """
    Запрос подтверждения актуальности кошелька.
    Может содержать TRC-20 адрес.
    """
    t = (text or "").strip()
    if not t:
        return False
    # Важный признак: есть слово "кошелек" и запрос/подтверждение
    return bool(CONFIRM_RE.search(t))

def is_wallet_request_ru_trc20(text: str) -> bool:
    """
    Запрос 'пришлите актуальный кошелёк' (обычно без адреса).
    Если адрес уже в тексте — обычно это НЕ запрос, кроме кейса подтверждения.
    """
    t = (text or "").strip()
    if not t:
        return False

    has_addr = bool(TRC20_RE.search(t))

    # 1) Если есть адрес и это просьба подтвердить актуальность — считаем запросом
    if has_addr and is_wallet_confirm_request_ru(t):
        return True

    # 2) Если есть адрес, но нет подтверждения — это скорее "дали кошелек", не запрос
    if has_addr:
        return False

    # 3) исключения
    if NEG_RE.search(t):
        return False

    # 4) обычный запрос на выдачу кошелька
    return bool(REQ_RE.search(t))

def is_funds_inbound_notice_ru(text: str) -> bool:
    """
    'Примите/зачислите средства' + ссылка на tronscan transaction.
    """
    t = (text or "").strip()
    if not t:
        return False
    return bool(TRONSCAN_TX_RE.search(t) and FUNDS_INBOUND_RE.search(t))

def install_handlers():
    @client.on(events.NewMessage)
    async def handler(event):
        chat = await event.get_chat()

        # ✅ слушаем только группы/супергруппы
        if isinstance(chat, User):
            return
        if isinstance(chat, Channel) and not getattr(chat, "megagroup", False):
            return

        text = event.raw_text or ""
        if not text.strip():
            return

        sender = await event.get_sender()
        sender_name = (
            getattr(sender, "username", None)
            or getattr(sender, "first_name", "")
            or "unknown"
        )
        chat_name = (
            getattr(chat, "title", None)
            or getattr(chat, "username", None)
            or "group"
        )

        target = ALERT_TARGET
        if str(target).lstrip("-").isdigit():
            target = int(target)

        # 1) Кейс: входящие средства / tronscan tx
        if is_funds_inbound_notice_ru(text):
            alert = (
                f"💸 *Поступление / Tx sent (TRC-20)*\n"
                f"👤 From: `{sender_name}`\n"
                f"💬 Source: `{chat_name}`\n\n"
                f"{text}"
            )
            await client.send_message(target, alert, parse_mode="md")
            return

        # 2) Кейс: запрос кошелька (включая 'подтвердите актуальность ... <адрес>')
        if is_wallet_request_ru_trc20(text):
            # Выделим тип, чтобы было понятно: "confirm" или "request"
            kind = "подтверждение" if is_wallet_confirm_request_ru(text) else "запрос"
            alert = (
                f"💼 *{kind.capitalize()} актуального кошелька (TRC-20)*\n"
                f"👤 From: `{sender_name}`\n"
                f"💬 Source: `{chat_name}`\n\n"
                f"{text}"
            )
            await client.send_message(target, alert, parse_mode="md")
            return
