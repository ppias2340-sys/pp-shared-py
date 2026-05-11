"""Shared Python utilities for Pedro's bot ecosystem.

Source-of-truth para módulos que históricamente se duplicaban byte-por-byte
en `bot-comprobantes-wa` y `bancos-comprobantes-matcher`:

    pp_shared.log_setup      → JSON logging + correlation_id ContextVar
    pp_shared.sentry_setup   → Sentry init opt-in via SENTRY_DSN env
    pp_shared.token_cascade  → warn cuando env tokens colapsaron al mismo valor

Usado vía submodule git en cada repo consumer:

    git submodule add https://github.com/ppias2340-sys/pp-shared-py.git lib/pp_shared

E instalado en el venv via `pip install -e lib/pp_shared` así los imports
`from pp_shared.log_setup import setup_logging_from_env` funcionan desde
cualquier módulo del consumer.
"""
