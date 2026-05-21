"""Tests for structured JSON logging."""

import json
import logging

from logging_config import JsonFormatter


def test_json_formatter_emits_valid_json() -> None:
    record = logging.LogRecord(
        name="capital.test",
        level=logging.INFO,
        pathname="f.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "capital.test"
    assert parsed["msg"] == "hello world"
    assert "ts" in parsed


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="capital.test",
            level=logging.ERROR,
            pathname="f.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=logging.sys.exc_info(),
        )
    parsed = json.loads(JsonFormatter().format(record))
    assert "ValueError" in parsed["exc"]
