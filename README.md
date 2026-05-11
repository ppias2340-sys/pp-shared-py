# pp-shared

Shared Python utilities for Pedro's ecosystem — extracted to keep
`bot-comprobantes-wa` and `bancos-comprobantes-matcher` in sync without
the copy-paste drift that historically caused subtle differences in
docstrings, logger names, and behavior.

## What's inside

| Module | Purpose |
|---|---|
| `pp_shared.log_setup` | Structured JSON logging + `correlation_id` ContextVar for end-to-end tracing |
| `pp_shared.sentry_setup` | Opt-in Sentry init via `SENTRY_DSN` env var (no-op if not set or sentry-sdk not installed) |
| `pp_shared.token_cascade` | Startup warning when derived tokens silently fall back to upstream (read/write boundary collapse) |

Each module exposes a `logger_name` kwarg so consumers can route their
own log namespace (`bot.sentry` vs `matcher_service.sentry`).

## Why opt-in for `sentry-sdk`

`sentry-sdk` is NOT a hard dep of this lib — it's only imported when
`SENTRY_DSN` is set AND the consumer has installed it. This keeps the
supply chain minimal for services that don't need Sentry.

```bash
# In the consumer service:
pip install sentry-sdk[fastapi]   # opt-in
export SENTRY_DSN="https://..."
```

## How to consume

Both consumers (`bot-comprobantes-wa`, `bancos-comprobantes-matcher`)
embed this repo as a **git submodule** under `lib/pp_shared/` and
install it editable:

```bash
# One-time setup in the consumer repo:
git submodule add https://github.com/ppias2340-sys/pp-shared-py.git lib/pp_shared

# In the consumer's deploy / venv bootstrap:
pip install -e ./lib/pp_shared
```

After that:

```python
from pp_shared.log_setup import setup_logging_from_env, set_correlation_id
from pp_shared.sentry_setup import init_sentry
from pp_shared.token_cascade import warn_on_token_cascade

setup_logging_from_env()
init_sentry(logger_name="bot.sentry")
warn_on_token_cascade(
    ("MATCHER_READ_TOKEN", os.getenv("MATCHER_READ_TOKEN", "")),
    ("WA_BRIDGE_TOKEN", os.getenv("WA_BRIDGE_TOKEN", "")),
    logger_name="bot.token_cascade",
)
```

## Sync workflow

When you edit any module here:

1. Run tests locally: `pytest`
2. Commit + push to `pp-shared-py`
3. In each consumer (`bot-comprobantes-wa`, `matcher-service`):
   - `cd lib/pp_shared && git pull origin main`
   - Commit the submodule pointer bump
   - Deploy with `pip install -e ./lib/pp_shared` (already in deploy.sh)

## Why submodule (not pip from git URL)

- **Source-of-truth guarantee**: the deployed code is exactly what's in
  the submodule pointer, no surprise pulls.
- **Tar-deploy works**: `bot-comprobantes-wa` deploys via `tar | ssh`,
  which means the submodule must be populated **locally** before tar.
  Git submodule clones it locally; pip-from-git would require git on the
  VPS.
- **Easy to edit in place** during dev: `pip install -e ./lib/pp_shared`
  means consumer reads from filesystem, so iteration is instant.

## Tests

```bash
pytest
```

Tests cover:
- JSON formatter emits required fields, includes correlation_id when
  set, omits when unset, includes extras, redacts exception messages
  (only exc_type, never str(exc)).
- Sentry init is idempotent, no-ops when DSN absent, no-ops when
  sentry-sdk uninstalled, routes logs to custom logger_name.
- Token cascade warns only when both tokens are equal AND non-empty,
  returns bool for instrumentation, routes to custom logger_name.

## License

Proprietary. Internal use only.
