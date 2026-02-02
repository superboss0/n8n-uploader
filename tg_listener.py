import os
import re
from telethon import events
from telethon.tl.types import User, Channel
from tg_sender import client  # используем тот же Telethon client и сессию

# Куда пересылать алерты (Finance. Internal)
ALERT_TARGET = os.environ.get("ALERT_TARGET", "4906022006")

# --- Regex: TRC-20 (TRON) address ---
TRC20_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33,35}\b")

# --- Regex: Tronscan tx link ---
TRONSCAN_TX_RE = re.compile(
    r"https?://(?:www\.)?tronscan\.org/#/transaction/[0-9a-fA-F]{16,}",
    re.IGNORECASE,
)

# Общий “корень” слова кошелек/кошелёк с опциональным мягким знаком
WALLET_STEM = r"кошел[её]ь?к"

# --- 1) Обычный запрос актуального кошелька (обычно БЕЗ адреса) ---
REQ_PATTERNS = [
    rf"\b(пришлите|скиньте|киньте|дайте|подскажите|предоставьте|нужен)\b.*\b{WALLET_STEM}\b",
    rf"\b(актуальный|на сегодня|сегодняшний)\b.*\b{WALLET_STEM}\b",
    rf"\b(на какой|куда)\b.*\b{WALLET_STEM}\b",
    rf"\b{WALLET_STEM}\b.*\b(на сегодня|актуальный|для пополнения|для при[её]ма|принять|принять средства)\b",
]
REQ_RE = re.compile("|".join(f"(?:{p})" for p in REQ_PATTERNS), re.IGNORECASE)

# --- 2) Подтверждение актуальности кошелька (может быть С адресом) ---
CONFIRM_VERB_RE = re.compile(
    r"\b(подтверд(ите|и|ить)|проверь(те|)|проверить|уточните|уточнить)\b",
    re.IGNORECASE,
)
CONFIRM_WORD_RE = re.compile(
    r"\b(актуальн(ость|ости|ый|ая|ен|на)|валидн(ость|ости|ый|ая|ен|а))\b",
    re.IGNORECASE,
)
WALLET_WORD_RE = re.compile(
    rf"\b{WALLET_STEM}(а|у|ом|и|ов)?\b",
    re.IGNORECASE,
)

# --- Исключения (не запрос кошелька) ---
NEG_RE = re.compile(
    rf"({WALLET_STEM} тот же|тот же {WALLET_STEM}|"
    r"был приход|поступлен|не вижу поступлен|"
    rf"сменить {WALLET_STEM}|заменить {WALLET_STEM}|друг(ой|ого) {WALLET_STEM}|чистый|"
    rf"{WALLET_STEM}а нет|нет {WALLET_STEM}а|не имею {WALLET_STEM}а|"
    rf"{WALLET_STEM}и для вывода)",
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
    - CONFIRM_WALLET: подтвердить актуальность/валидность кошелька (адрес может быть или не быть)
    - REQUEST_WALLET: обычный запрос кошелька без адреса
    - если есть адрес, но нет CONFIRM — это не запрос (скорее "дали кошелек")
    """
    t = (text or "").strip()
    if not t:
        return False

    # 0) Confirm всегда считаем запросом (даже если адрес не распознан regex-ом)
    if is_wallet_confirm_request_ru(t):
        return True

    has_addr = bool(TRC20_RE.search(t))

    # 1) Адрес без confirm => не считаем запросом (скорее "кошелек: ...")
    if has_addr:
        return False

    # 2) исключения
    if NEG_RE.search(t):
        return False

    # 3) обычный запрос
    return bool(REQ_RE.search(t))


def is_funds_inbound_notice_ru(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(TRONSCAN_TX_RE.search(t) and FUNDS_INBOUND_RE.search(t))


def detect_intent(text: str) -> str | None:
    if is_funds_inbound_notice_ru(text):
        return "TX_SENT"

    # CONFIRM приоритетнее, чем обычный запрос
    if is_wallet_confirm_request_ru(text):
        return "CONFIRM_WALLET"

    if is_wallet_request_ru_trc20(text):
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

