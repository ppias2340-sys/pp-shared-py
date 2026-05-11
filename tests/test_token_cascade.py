"""Tests para warn_on_token_cascade — defensa contra silent token fallback.

Patrón: `MATCHER_READ_TOKEN` defaulta a `WA_BRIDGE_TOKEN`, etc. Cuando se
deploya con un solo token seteado, el read/write split se anula
silentemente. Solución: log.warning visible al startup. NO fail-fast —
eso rompería deployments existentes — pero al menos sale en los logs.
"""

from __future__ import annotations

import logging

from pp_shared.token_cascade import warn_on_token_cascade


def test_no_warning_when_tokens_distinct(caplog):
    with caplog.at_level(logging.WARNING):
        warn_on_token_cascade(("A", "alpha"), ("B", "beta"))
    assert "cascade" not in caplog.text.lower()


def test_warning_when_tokens_equal_and_nonempty(caplog):
    with caplog.at_level(logging.WARNING):
        warn_on_token_cascade(("MATCHER_READ_TOKEN", "shared"), ("WA_BRIDGE_TOKEN", "shared"))
    assert "cascade" in caplog.text.lower()
    assert "MATCHER_READ_TOKEN" in caplog.text
    assert "WA_BRIDGE_TOKEN" in caplog.text


def test_no_warning_when_both_empty(caplog):
    """Both empty = dev mode (covered by WA_ALLOW_NO_TOKEN), don't double-warn."""
    with caplog.at_level(logging.WARNING):
        warn_on_token_cascade(("MATCHER_READ_TOKEN", ""), ("WA_BRIDGE_TOKEN", ""))
    assert "cascade" not in caplog.text.lower()


def test_no_warning_when_one_empty(caplog):
    """One empty = the cascade didn't actually fire."""
    with caplog.at_level(logging.WARNING):
        warn_on_token_cascade(("X", ""), ("Y", "set"))
    assert "cascade" not in caplog.text.lower()


def test_returns_true_when_warning_emitted(caplog):
    """Return value usable for tests + counter instrumentation."""
    with caplog.at_level(logging.WARNING):
        result = warn_on_token_cascade(("A", "shared"), ("B", "shared"))
    assert result is True


def test_returns_false_when_no_warning(caplog):
    with caplog.at_level(logging.WARNING):
        result = warn_on_token_cascade(("A", "alpha"), ("B", "beta"))
    assert result is False


def test_uses_custom_logger_name(caplog):
    """logger_name kwarg routes the warning to a service-specific namespace."""
    caplog.set_level(logging.WARNING, logger="bot.token_cascade")
    warn_on_token_cascade(
        ("MATCHER_READ_TOKEN", "shared"),
        ("WA_BRIDGE_TOKEN", "shared"),
        logger_name="bot.token_cascade",
    )
    assert any(
        "cascade" in r.getMessage().lower() and r.name == "bot.token_cascade"
        for r in caplog.records
    )
