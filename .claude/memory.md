# pp-shared-py â€” project memory

## Overview
Shared Python utilities for Pedro's ecosystem. Extracted to keep `bot-comprobantes-wa` and `bancos-comprobantes-matcher` in sync without copy-paste drift.

## Modules
- `pp_shared.log_setup` â€” Structured JSON logging + `correlation_id` ContextVar for end-to-end tracing
- `pp_shared.sentry_setup` â€” Opt-in Sentry init via `SENTRY_DSN` env var (no-op if not set)
- `pp_shared.token_cascade` â€” Startup warning when derived tokens silently fall back to upstream

## Stack
- **Python 3.12** + pytest
- **Optional deps**: sentry-sdk (opt-in only, not a hard dep)

## Status
- Shared library consumed by multiple bots
- Vendored into consumer projects (bot-comprobantes-wa, matcher-service)
- No memory file existed before this update

