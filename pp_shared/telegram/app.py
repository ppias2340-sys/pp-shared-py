import logging
from typing import Any, Callable

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pp_shared.log_setup import setup_logging_from_env

log = logging.getLogger(__name__)


async def _default_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled handler error: %s", context.error)


def build_application(
    token: str,
    *,
    command: str,
    command_handler: Callable,
    callback_handler: Callable | None = None,
    callback_pattern: str | None = None,
    message_handler: Callable | None = None,
    error_handler: Callable = _default_error_handler,
    post_init: Callable[[Application], Any] | None = None,
    chat_filter: int | None = None,
    connect_timeout: float = 15,
    read_timeout: float = 15,
    write_timeout: float = 15,
    pool_timeout: float = 15,
    connection_pool_size: int = 10,
    allowed_updates: list[str] | None = None,
) -> Application:
    setup_logging_from_env()

    filters_kw = {}
    if chat_filter is not None:
        filters_kw["filters"] = filters.Chat(chat_filter)

    builder = (
        ApplicationBuilder()
        .token(token)
        .connect_timeout(connect_timeout)
        .read_timeout(read_timeout)
        .write_timeout(write_timeout)
        .pool_timeout(pool_timeout)
        .connection_pool_size(connection_pool_size)
    )

    if post_init is not None:
        builder.post_init(post_init)

    app = builder.build()

    app.add_handler(CommandHandler(command, command_handler, **filters_kw))

    if callback_handler is not None:
        kw = {}
        if callback_pattern is not None:
            kw["pattern"] = callback_pattern
        app.add_handler(CallbackQueryHandler(callback_handler, **kw))

    if message_handler is not None:
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler, **filters_kw))

    if error_handler is not None:
        app.add_error_handler(error_handler)

    return app
