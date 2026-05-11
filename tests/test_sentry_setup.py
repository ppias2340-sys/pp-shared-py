"""Sentry init es opt-in: requiere `sentry-sdk` instalado + `SENTRY_DSN` env."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from pp_shared import sentry_setup


@pytest.fixture(autouse=True)
def _reset_initialized():
    """Each test starts with init flag False."""
    sentry_setup._initialized = False
    yield
    sentry_setup._initialized = False


def test_init_returns_false_when_no_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert sentry_setup.init_sentry() is False


def test_init_returns_false_when_sentry_sdk_not_installed(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert sentry_setup.init_sentry() is False


def test_init_calls_sentry_init_when_present(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    result = sentry_setup.init_sentry()
    assert result is True
    fake.init.assert_called_once()
    call_kwargs = fake.init.call_args.kwargs
    assert call_kwargs["dsn"] == "https://example@sentry.io/1"
    assert call_kwargs.get("environment") == "production"


def test_init_is_idempotent(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    assert sentry_setup.init_sentry() is True
    assert sentry_setup.init_sentry() is True
    fake.init.assert_called_once()  # not twice


def test_init_uses_custom_logger_name(monkeypatch, caplog):
    """logger_name kwarg routes init/error logs to a service-specific namespace."""
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    import logging
    caplog.set_level(logging.INFO, logger="bot.sentry")
    sentry_setup.init_sentry(logger_name="bot.sentry")
    assert any(
        "Sentry initialized" in r.getMessage() and r.name == "bot.sentry"
        for r in caplog.records
    )
