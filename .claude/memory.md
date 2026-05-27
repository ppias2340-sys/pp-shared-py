# pp-shared-py â€” project memory

Last updated: 2026-05-26

Language preference: Speak in English by default. If Pedro explicitly asks for Spanish, switch to Spanish for that session.

## Overview
Shared Python utilities for Pedro's ecosystem. Extracted to keep bot-comprobantes-wa and matcher-service in sync without copy-paste drift.

## Modules
- `pp_shared.log_setup` — structured JSON logging + correlation_id ContextVar
- `pp_shared.sentry_setup` — opt-in Sentry init via SENTRY_DSN env var
- `pp_shared.token_cascade` — startup warning on derived token fallback

## Stack
- Python 3.12 + pytest
- Optional: sentry-sdk

## Commands
- `pytest` — run tests

## TODOs
- (none tracked)

## Changelog
- 2026-05-26: Initial memory file created

