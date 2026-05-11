"""Structured JSON logging + correlation ID context.

Compartido entre bot-comprobantes-wa y bancos-comprobantes-matcher para
permitir tracing end-to-end de un comprobante via correlation_id:

    journalctl -u bot-comprobantes-wa-bot.service -o json | jq 'select(.correlation_id == "receipt:179")'
    journalctl -u matcher-service                 -o json | jq 'select(.correlation_id == "receipt:179")'

Ambos servicios siguen el mismo correlation_id (basado en whatsapp_message_id
o receipt_id) → reconstruir el flow es 2 greps en lugar de un manual join.

Por qué `contextvars` (no `threading.local`):
- FastAPI (asyncio) en el bot: corutinas reusan threads, threading.local
  pierde aislamiento. ContextVar sobrevive a `await` correctamente.
- Matcher: hoy single-thread pero se mueve a async-style en el notify drain;
  ContextVar es la única opción consistente cross-boundary.

Por qué solo type del exception (no `str(exc)`):
- `str(exc)` en errores HTTP/aiohttp/httpx embebe URLs que pueden traer
  tokens en query params. Ver `feedback_aiohttp_clienterror_url_leak`.
- Type-only siempre es safe.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone

# Set por endpoints / handlers, leído por el formatter.
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

_LOG_RECORD_BUILTIN_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formatea cada log record como una línea JSON.

    Campos siempre presentes: `ts`, `level`, `name`, `msg`.
    Si correlation_id está set en el ContextVar, se incluye.
    `extra={}` fields del logger se mergean al top-level.
    Excepciones se reportan como `exc_type` SOLO (nunca `str(exc)`).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        cid = correlation_id.get()
        if cid:
            payload["correlation_id"] = cid

        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Unknown"

        # Mergear extras (`logger.info("x", extra={"k": v})`).
        for key, value in record.__dict__.items():
            if key in _LOG_RECORD_BUILTIN_ATTRS:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        return json.dumps(payload, ensure_ascii=False, default=str)


_setup_done = False


def setup_json_logging(level: int = logging.INFO, force: bool = False) -> None:
    """Configura el root logger con JsonFormatter en stderr.

    Idempotente: re-llamadas no agregan handlers duplicados.
    Pasa `force=True` para reemplazar la config previa (útil en tests).
    """
    global _setup_done
    if _setup_done and not force:
        return

    root = logging.getLogger()
    root.setLevel(level)
    # Reemplaza handlers existentes (no acumula).
    root.handlers = []
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    _setup_done = True


def setup_logging_from_env() -> None:
    """Decide JSON vs text según `JSON_LOGS` env var.

    Default: text (compat con `journalctl` lectura humana).
    `JSON_LOGS=1` activa JSON (recomendado en VPS para parseo).
    """
    if os.getenv("JSON_LOGS", "0").strip() == "1":
        setup_json_logging()
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        )


def set_correlation_id(value: str | None) -> None:
    """Helper para setear el correlation_id desde un endpoint.

    Pasá string vacío o None para clear. Acepta cualquier identifier
    (whatsapp_message_id, receipt_id, uuid4, etc).
    """
    correlation_id.set(value or "")


def get_correlation_id() -> str:
    return correlation_id.get()
