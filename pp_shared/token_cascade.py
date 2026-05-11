"""Token cascade detection — warns at startup when env tokens collapsed.

Compartido entre bot-comprobantes-wa y bancos-comprobantes-matcher. Cada
servicio tiene env vars que defaultean a otras (MATCHER_READ_TOKEN →
WA_BRIDGE_TOKEN, MATCHER_NOTIFY_TOKEN → MATCHER_READ_TOKEN, etc).
Convenient para dev (un solo token), pero en prod una misconfig puede
colapsar el read/write boundary silently.

Per `feedback_token_cascade_silent_open.md`: cada derived token necesita
hard-fail al startup; failing that, al menos loud observability para que
un operator note en logs / Sentry.

Uso (cualquier servicio consumer):

    from pp_shared.token_cascade import warn_on_token_cascade

    warn_on_token_cascade(
        ("MATCHER_READ_TOKEN", MATCHER_READ_TOKEN),
        ("WA_BRIDGE_TOKEN", WA_BRIDGE_TOKEN),
    )

`logger_name` permite que cada servicio elija su namespace de logger
(default: `pp_shared.token_cascade`).
"""

from __future__ import annotations

import logging


def warn_on_token_cascade(
    derived: tuple[str, str],
    upstream: tuple[str, str],
    *,
    logger_name: str = "pp_shared.token_cascade",
) -> bool:
    """Log a WARNING if `derived` token silently fell back to `upstream`.

    Returns True when a warning was emitted (useful for tests + counter
    instrumentation).

    `logger_name` controla qué logger se usa — default `pp_shared.token_cascade`,
    pero cada consumer puede pasar su propio (`bot.token_cascade`,
    `matcher_service.token_cascade`) para que los logs queden en su namespace.
    """
    log = logging.getLogger(logger_name)
    derived_name, derived_val = derived
    upstream_name, upstream_val = upstream

    if not derived_val or not upstream_val:
        # Either is empty → cascade didn't fire (or dev mode).
        return False
    if derived_val != upstream_val:
        return False

    log.warning(
        "TOKEN CASCADE: %s == %s — read/write boundary collapsed. "
        "Set %s explicitly to a distinct value to restore the split.",
        derived_name, upstream_name, derived_name,
    )
    return True
