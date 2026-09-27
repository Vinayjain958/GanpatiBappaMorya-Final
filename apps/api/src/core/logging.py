"""Structured logging foundation."""

from __future__ import annotations

import logging
import re
import sys

# httpx's own request logger (INFO level) logs the full request URL
# verbatim, including query parameters — several adapters (OpenWeather,
# Ticketmaster) pass their API key as a query param (`appid`, `apikey`),
# so without this filter every outbound request line leaked the live key
# into stdout/server logs. Redacts the value of any of these parameter
# names wherever they appear in a log message, regardless of which
# logger emitted it (defense in depth beyond just the httpx logger).
_SENSITIVE_QUERY_PARAMS = ("appid", "apikey", "api_key", "key", "token", "access_token")
_REDACT_PATTERN = re.compile(
    r"(" + "|".join(_SENSITIVE_QUERY_PARAMS) + r")=([^&\s\"']+)",
    re.IGNORECASE,
)


class _RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpx's request logger uses %s-style templates (record.msg is
        # the template; the actual URL, including any query-param key,
        # lives in record.args as a separate object — checking/redacting
        # only record.msg (as a naive string-substitution approach would)
        # never sees the key at all, since it isn't interpolated until
        # the Formatter runs downstream of every Filter. Redact the fully
        # rendered message instead and collapse to a plain string so the
        # Formatter doesn't re-run %-substitution on it.
        rendered = record.getMessage()
        if _REDACT_PATTERN.search(rendered):
            record.msg = _REDACT_PATTERN.sub(r"\1=***REDACTED***", rendered)
            record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s :: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        root.addHandler(handler)
        root.setLevel(level)

    # A Filter attached directly to the *logger* (not a handler) runs on
    # every record that logger emits regardless of which handler(s)
    # eventually process it, so this applies even when uvicorn's own
    # startup has already configured root handlers before this function
    # runs (in which case the block above is skipped entirely) — the
    # `if root.handlers: return` short-circuit previously skipped
    # attaching the redaction filter too, silently leaking API keys
    # (OpenWeather `appid`, Ticketmaster `apikey`) into server logs on
    # every real request under uvicorn's default logging setup.
    httpx_logger = logging.getLogger("httpx")
    if not any(isinstance(f, _RedactSecretsFilter) for f in httpx_logger.filters):
        httpx_logger.addFilter(_RedactSecretsFilter())
