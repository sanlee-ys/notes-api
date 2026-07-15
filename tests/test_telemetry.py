"""Tests for the optional OpenTelemetry tracing layer (notes_api/telemetry.py).

Offline (no collector, no network): (1) the SDK only activates when
NOTES_API_TRACING is set, so a normal run and the rest of the suite stay no-op;
(2) a classify_and_writeback() run emits the span tree — the task span plus a
child POST span — with the HTTP and enrichment-status attributes, captured
through an in-memory exporter injected via the tracer accessor (the global
provider is never touched, so the test stays isolated).
"""

import pytest

from notes_api import tasks
from notes_api.models import Note
from notes_api.telemetry import _enabled, setup_tracing


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_enabled_true_for_truthy_values(monkeypatch, value):
    monkeypatch.setenv("NOTES_API_TRACING", value)
    assert _enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "  "])
def test_enabled_false_for_off_values(monkeypatch, value):
    monkeypatch.setenv("NOTES_API_TRACING", value)
    assert _enabled() is False


def test_setup_tracing_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("NOTES_API_TRACING", raising=False)
    from notes_api import telemetry

    monkeypatch.setattr(telemetry, "_CONFIGURED", False)
    assert setup_tracing() is False


def test_enrichment_emits_span_tree_with_attributes(monkeypatch, session_factory):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(tasks, "get_tracer", lambda: tracer)

    seed = session_factory()
    note = Note(title="Budget", content="Senate approves cyber budget")
    note.tags = ["mine"]
    seed.add(note)
    seed.commit()
    seed.refresh(note)
    note_id = note.id
    seed.close()

    def _post(*a, **k):
        return _FakeResponse({"category": "procurement", "operational_domain": "cyber"})

    monkeypatch.setattr(tasks.httpx, "post", _post)
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

    tasks.classify_and_writeback(note_id, "Senate approves cyber budget")

    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert "classify_and_writeback" in spans
    assert "POST /classify" in spans

    http_span = spans["POST /classify"]
    assert http_span.attributes["http.request.method"] == "POST"
    assert http_span.attributes["url.full"] == "http://fake-classifier/classify"
    assert http_span.attributes["http.response.status_code"] == 200

    task_span = spans["classify_and_writeback"]
    assert task_span.attributes["notes_api.note_id"] == note_id
    assert task_span.attributes["notes_api.enrichment.status"] == "done"
    assert task_span.attributes["notes_api.enrichment.attempts"] == 1


def test_enrichment_span_off_by_default_is_harmless(monkeypatch, session_factory):
    # With tracing off (no NOTES_API_TRACING), the no-op spans must not disturb
    # the existing behavior: a first-attempt success still writes back and no
    # status_code is ever read off the fake response (it has none here on purpose).
    class _NoStatusResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"category": "policy", "operational_domain": "sea"}

    seed = session_factory()
    note = Note(title="t", content="c")
    seed.add(note)
    seed.commit()
    seed.refresh(note)
    note_id = note.id
    seed.close()

    monkeypatch.setattr(tasks.httpx, "post", lambda *a, **k: _NoStatusResponse())
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

    tasks.classify_and_writeback(note_id, "c")

    check = session_factory()
    refreshed = check.query(Note).filter(Note.id == note_id).first()
    check.close()
    assert refreshed.enrichment_status == "done"
    assert set(refreshed.tags) == {"category:policy", "domain:sea"}
