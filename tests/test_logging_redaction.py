from infra.logging import get_logger
import json
import logging

# Simple test ensuring that sensitive env vars are not automatically leaked unless explicitly logged.
# We simulate by setting an env var and ensuring logger doesn't emit it unless we add it to extra.

def test_logger_does_not_auto_include_env_value(capfd, monkeypatch):  # pragma: no cover - partial run artifact
    monkeypatch.setenv("TEST_SECRET_TOKEN", "super-secret-value")
    logger = get_logger("test")
    logger.info("hello", extra={"event": "unit"})
    out = capfd.readouterr().out
    assert "super-secret-value" not in out


def test_logger_includes_extra_when_explicit(capfd):  # pragma: no cover
    logger = get_logger("test2")
    buffer: list[str] = []
    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
            from infra.logging import JsonFormatter
            fmt = JsonFormatter()
            buffer.append(fmt.format(record))
    lh = ListHandler()
    logger.addHandler(lh)
    try:
        logger.info("explicit", extra={"event": "unit", "token_snippet": "abc123"})
        assert buffer, "no log output captured"
        parsed = json.loads(buffer[-1])
        # token_snippet contains sensitive substring; should be redacted
        assert parsed.get("token_snippet") == "[REDACTED]"
    finally:
        logger.removeHandler(lh)
