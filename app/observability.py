"""Optional Sentry Agent Tracing. Off unless SENTRY_DSN is set. Never sends prompt text or PII."""
from __future__ import annotations

import contextlib
import os

try:  # sentry-sdk is optional
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None


def init() -> bool:
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn or sentry_sdk is None:
        return False
    sentry_sdk.init(dsn=dsn, traces_sample_rate=1.0, send_default_pii=False)
    return True


@contextlib.contextmanager
def llm_span(job: str, provider: str, model: str):
    """Span for one model call. Yields a setter for token counts; no prompt content is recorded."""
    if sentry_sdk is None or not sentry_sdk.is_initialized():
        yield lambda **kw: None
        return
    with sentry_sdk.start_span(op="gen_ai.chat", name=f"{job} {model}", attributes={
            "gen_ai.operation.name": "chat", "gen_ai.provider.name": provider,
            "gen_ai.request.model": model, "firststep.job": job}) as span:
        yield lambda **kw: [span.set_data(k, v) for k, v in kw.items()]


@contextlib.contextmanager
def work_span(name: str, **attrs):
    if sentry_sdk is None or not sentry_sdk.is_initialized():
        yield
        return
    with sentry_sdk.start_span(op="firststep." + name, name=name, attributes=attrs):
        yield