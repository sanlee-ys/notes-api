"""Optional OpenTelemetry tracing for the classifier enrichment seam.

The background enrichment task (``tasks.classify_and_writeback``) is instrumented
against the OpenTelemetry **API**, whose default tracer is a no-op that records
nothing and costs nothing. The **SDK** that actually records and exports spans is
configured only when ``NOTES_API_TRACING`` is set (via :func:`setup_tracing`,
called at app startup) — so a normal run and the offline test suite are
unaffected unless you opt in.

This mirrors the tracing in ``kb-agent`` and the classifier, so all three
services speak the same observability language. Here the traced thing is the
cross-service ``/classify`` HTTP hop (SYS-004): each enrichment task becomes a
span, with a child span per HTTP attempt so retries are visible.

Enable it::

    NOTES_API_TRACING=1 uvicorn notes_api.main:app --app-dir src   # spans to stderr
    NOTES_API_TRACING=1 OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
        uvicorn notes_api.main:app --app-dir src                   # + a collector

The OTLP exporter is an optional extra (``uv sync --extra otlp``); the console
exporter needs no infrastructure and is always available.
"""

from __future__ import annotations

import os
import sys

from opentelemetry import trace
from opentelemetry.trace import Tracer

_TRACER_NAME = "notes-api"
_CONFIGURED = False


def _enabled() -> bool:
    """Return whether tracing is switched on via ``NOTES_API_TRACING``.

    Anything but an obvious off value counts as on, so ``1`` / ``true`` enable it
    while ``0`` / ``false`` / ``no`` / empty leave it off.
    """
    return os.environ.get("NOTES_API_TRACING", "").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
    )


def setup_tracing() -> bool:
    """Configure the OpenTelemetry SDK if tracing is enabled. Idempotent.

    When enabled, installs a console span exporter (to stderr, so it never
    pollutes stdout) and, if ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set and the OTLP
    extra is installed, an OTLP exporter alongside it. When disabled, leaves the
    API's global no-op provider in place and does nothing.

    Returns:
        True if the SDK is now active, False if tracing was left as the no-op
        default. Safe to call repeatedly; only the first enabled call configures
        the provider.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return True
    if not _enabled():
        return False

    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: _TRACER_NAME}))
    provider.add_span_processor(
        SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stderr))
    )

    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError:
            print(
                "notes-api: OTEL_EXPORTER_OTLP_ENDPOINT is set but the OTLP "
                "exporter is not installed (uv sync --extra otlp). Using the "
                "console exporter only.",
                file=sys.stderr,
            )

    trace.set_tracer_provider(provider)
    _CONFIGURED = True
    return True


def get_tracer() -> Tracer:
    """Return the notes-api tracer from whatever provider is installed.

    Resolves against the global provider at call time, so it is the no-op tracer
    until :func:`setup_tracing` installs a real SDK provider.
    """
    return trace.get_tracer(_TRACER_NAME)
