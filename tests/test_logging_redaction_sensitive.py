from infra.logging import get_logger
import json
import logging

def test_sensitive_key_redacted():
    logger = get_logger("redact")
    buf: list[str] = []
    class ListHandler(logging.Handler):
        def emit(self, record):  # noqa: D401
            from infra.logging import JsonFormatter
            buf.append(JsonFormatter().format(record))
    h = ListHandler()
    logger.addHandler(h)
    try:
        logger.info("secret test", extra={"api_key": "XYZ123", "token_value": "abcdef"})
        assert buf, "no log captured"
        parsed = json.loads(buf[-1])
        assert parsed.get("api_key") == "[REDACTED]"
        # token_value key not exact but includes 'token'; should be redacted
        assert parsed.get("token_value") == "[REDACTED]"
    finally:
        logger.removeHandler(h)
