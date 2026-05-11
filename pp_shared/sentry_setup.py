"""Sentry integration — opt-in via env vars.

Compartido entre bot-comprobantes-wa y bancos-comprobantes-matcher.
Cada servicio llama `init_sentry()` al startup; si `SENTRY_DSN` no está
set, no-op silencioso.

Por qué opt-in:
- `sentry-sdk` no es una dep core; sumarla aumenta supply chain.
- Pedro decide cuándo activarlo (cuesta tokens del free tier).

Cómo activarlo:
1. `pip install sentry-sdk[fastapi]` en el venv del servicio.
2. Setear `SENTRY_DSN=https://...@sentry.io/...` en el `.env` del VPS.
3. Opcional: `SENTRY_ENVIRONMENT=production` (default `production`).
4. Restart el servicio.

A partir de ese momento, excepciones no manejadas se reportan
automáticamente. El correlation_id del log_setup también se incluye
como tag.

`logger_name` permite cada servicio elegir su logger root (`bot.sentry`
vs `matcher_service.sentry`) — defaultea a `pp_shared.sentry`.
"""

from __future__ import annotations

import logging
import os

_initialized = False


def init_sentry(*, logger_name: str = "pp_shared.sentry") -> bool:
    """Inicializa Sentry si DSN está set Y sentry_sdk está instalado.

    Devuelve True si quedó activo, False si se skipeó (silencioso).
    Idempotente: re-llamadas no re-inicializan.

    `logger_name` controla qué logger se usa para los mensajes de status
    (init OK, init failed, etc). Cada servicio consumer pasa su propio
    namespace para que los logs queden ruteados correctamente.
    """
    global _initialized
    log = logging.getLogger(logger_name)
    if _initialized:
        return True

    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        log.info("SENTRY_DSN set but sentry-sdk not installed — skipping init")
        return False

    if sentry_sdk is None:
        # Test path: monkeypatched to None to simulate missing module.
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "production").strip() or "production",
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0") or "0"),
            send_default_pii=False,  # never PII to a 3rd party
            release=os.getenv("SENTRY_RELEASE", "") or None,
        )
    except Exception as exc:
        # Sentry init failure must NEVER block service startup.
        log.warning("sentry init failed type=%s — continuing without Sentry", type(exc).__name__)
        return False

    _initialized = True
    log.info("Sentry initialized")
    return True
