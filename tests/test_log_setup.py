"""Tests para el JSON logger + correlation ID."""
from __future__ import annotations

import io
import json
import logging

import pytest

from pp_shared import log_setup


@pytest.fixture(autouse=True)
def _reset_correlation_id():
    log_setup.correlation_id.set("")
    yield
    log_setup.correlation_id.set("")


def _capture_log(level=logging.INFO) -> tuple[logging.Logger, io.StringIO]:
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(log_setup.JsonFormatter())
    logger = logging.getLogger("test_log_setup")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    return logger, buf


def test_json_formatter_emits_valid_json_with_required_fields():
    logger, buf = _capture_log()
    logger.info("hola %s", "mundo")
    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["msg"] == "hola mundo"
    assert record["level"] == "INFO"
    assert record["name"] == "test_log_setup"
    assert "ts" in record


def test_json_formatter_includes_correlation_id_when_set():
    log_setup.correlation_id.set("wamid:abc123")
    logger, buf = _capture_log()
    logger.info("processed")
    record = json.loads(buf.getvalue().strip())
    assert record.get("correlation_id") == "wamid:abc123"


def test_json_formatter_omits_correlation_id_when_unset():
    logger, buf = _capture_log()
    logger.info("processed")
    record = json.loads(buf.getvalue().strip())
    assert "correlation_id" not in record


def test_json_formatter_includes_extra_fields():
    logger, buf = _capture_log()
    logger.info("matched", extra={"comp_id": 179, "score": 80.86})
    record = json.loads(buf.getvalue().strip())
    assert record["comp_id"] == 179
    assert record["score"] == 80.86


def test_json_formatter_includes_exception_type_no_str():
    logger, buf = _capture_log()
    try:
        raise ValueError("a secret token=AAAA could leak here")
    except ValueError:
        logger.exception("call failed")
    record = json.loads(buf.getvalue().strip())
    # exception type yes, message NO (would leak secrets per feedback_aiohttp)
    assert record.get("exc_type") == "ValueError"
    assert "AAAA" not in json.dumps(record)


def test_setup_json_logging_is_idempotent():
    log_setup.setup_json_logging(force=True)
    handlers_after_first = list(logging.getLogger().handlers)
    log_setup.setup_json_logging(force=False)
    handlers_after_second = list(logging.getLogger().handlers)
    assert len(handlers_after_first) == len(handlers_after_second)


def test_set_get_correlation_id_round_trip():
    log_setup.set_correlation_id("xyz")
    assert log_setup.get_correlation_id() == "xyz"
    log_setup.set_correlation_id(None)
    assert log_setup.get_correlation_id() == ""
