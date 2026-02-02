import os
import re
from telethon import events
from telethon.tl.types import User, Channel
from tg_sender import client  # используем тот же Telethon client и сессию

# Куда пересылать алерты (Finance. Internal)
ALERT_TARGET = os.environ.get("ALERT_TARGET", "4906022006")

# --- Regex: TRC-20 (TRON) address ---
TRC20_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")

# --- Regex: Tronscan tx link ---
TRONSCAN_TX_RE = re.compile(
    r"https?://(?:www\.)?tronscan\.org/#/transaction/[0-9a-fA-F]{16,}",
    re.IGNORECASE,
)

# --- 1) Обычный запрос актуального кошелька (обычно БЕЗ адреса) ---
REQ_PATTERNS = [
    r"\b(пришлите|скиньте|киньте|дайте|подскажите|предоставьте|нужен)\b.*\bкошел[её]к\b",
    r"\b(актуальный|на сегодня|сегодняшний)\b.*\bкошел[её]к\b",
    r"\b(на какой|куда)\b.*\bкошел[её]к\b",
    r"\bкошел[её]к\b.*\b(на сегодня|актуальный|для пополнения|для при[её]ма|принять|принять средства)\b",
]
REQ_RE = re.compile("|".join(f"(?:{p})" for p in REQ_PATTERNS), re.IGNORECASE)

# --- 2) Подтверждение актуальности кошелька (может быть С адресом) ---
# Комбо-детектор: глагол подтверждения + слово актуальности/валидности + слово кошелек
CONFIRM_VERB_RE = re.compile(
    r"\b(подтверд(ите|и|ить)|проверь(те|)|проверить|уточните|уточнить)\b",
    re.IGNORECASE,
)
CONFIRM_WORD_RE = re.compile(
    r"\b(актуальн(ость|ости|ый|ая|ен|на)|валидн(ость|ости|ый|ая|ен|а))\b",
    re.IGNORECASE,
)
WALLET_WORD_RE = re.compile(
    r"\bкошел[её]к(а|у|ом|и|ов)?\b",
    re.IGNORECASE,
)

# --- 3) "Примите средства" + tronscan tx ---
FUNDS_INBOUND_RE = re.compile(
    r"\b(примите|зачислите|пополнени[ея]|пополним|пополнили|отправили|"
    r"отправили средства|средства для пополнения|на пополнение)\b",
    re.IGNORECASE,
)

# --- Исключения (не запрос кошелька) ---
NEG_RE = re.compile(
    r"(кошел[её]к тот же|тот же кошел[её]к|"
    r"был приход|поступлен|не вижу поступлен|"
    r"сменить кошел[её]к|заменить кошел[её]к|друг(ой|ого) кошел[её]к|чистый|"
    r"кошел[её]ка нет|нет кошел[её]ка|не имею кошел[её]ка|"
    r"кошел[её]ки для вывода)",
    re.IGNORECASE,
)


def extract_trc20_addresses(text: str) -> list[str]:
    if not text:
        return []
    # уникализируем, сохраняя порядок
    seen = set()
    out = []
    for m in TRC20_RE.findall(text):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def is_wallet_confirm_request_ru(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(
        CONFIRM_VERB_RE.search(t)
        and CONFIRM_WORD_RE.search(t)
        and WALLET_WORD_RE.search(t)
    )


def is_wallet_request_ru_trc20(text: str) -> bool:
    """
    Запрос кошелька:
    - если есть адрес + confirm => True (CONFIRM_WALLET)
    - если есть адрес без confirm => False (скорее "дали кошелек")
    - если нет адреса => обычный запрос REQ_RE (REQUEST_WALLET), кроме NEG_RE
    """
    t = (text or "").strip()
    if not t:
        return False

    has_addr = bool(TRC20_RE.search(t))

    # Адрес + подтверждение актуальности => это запрос
    if has_addr and is_wallet_confirm_request_ru(t):
        return True

    # Адрес без confirm => не считаем запросом (скорее просто "кошелек: ...")
    if has_addr:
        return False

    # исключения
    if NEG_RE.search(t):
        return False

    # обычный запрос
    return bool(REQ_RE.search(t))


def is_funds_inbound_notice_ru(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(TRONSCAN_TX_RE.search(t) and FUNDS_INBOUND_RE.search(t))


def detect_intent(text: str) -> str | None:
    """
    Возвращает intent:
      - TX_SENT
      - CONFIRM_WALLET
      - REQUEST_WALLET
      - None
    """
    if is_funds_inbound_notice_ru(text):
        return "TX_SENT"

    if is_wallet_request_ru_trc20(text):
        # если есть confirm-смысл — это CONFIRM_WALLET
        if is_wallet_confirm_request_ru(text):
            return "CONFIRM_WALLET"
        return "REQUEST_WALLET"

    return None


def install_handlers():
    @client.on(events.NewMessage)
    async def handler(event):
        chat = await event.get_chat()

        # ✅ слушаем только группы/супергруппы
        if isinstance(chat, User):
            return
        if isinstance(chat, Channel) and not getattr(chat, "megagroup", False):
            return

        text = (event.raw_text or "").strip()
        if not text:
            return

        intent = detect_intent(text)
        if not intent:
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

        wallets = extract_trc20_addresses(text)
        wallet_line = f"\n🔑 Wallet: `{wallets[0]}`" if wallets else ""

        alert = (
            f"🚨 *INTENT:* `{intent}`\n"
            f"👤 From: `{sender_name}`\n"
            f"💬 Source: `{chat_name}`"
            f"{wallet_line}\n\n"
            f"{text}"
        )

        await client.send_message(target, alert, parse_mode="md")

