import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class SendResult:
    ok: bool
    status_code: int = 0
    error: str | None = None


def send_telegram_message(
    bot_token: str | None,
    chat_id: str | None,
    text: str,
    *,
    message_thread_id: int | None = None,
    parse_mode: str = "HTML",
    timeout: int = 15,
) -> SendResult:
    if not bot_token or not chat_id:
        return SendResult(ok=False, error="missing_token_or_chat")

    import requests

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=timeout,
        )
        return SendResult(ok=resp.ok, status_code=resp.status_code)
    except requests.RequestException as e:
        log.warning("Telegram send failed: %s", type(e).__name__)
        return SendResult(ok=False, error=type(e).__name__)
