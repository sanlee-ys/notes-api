"""Unit tests for the SYS-005 classify-and-writeback enrichment logic."""

import logging

import httpx

from notes_api import tasks
from notes_api.models import Note
from notes_api.tasks import (
    CLASSIFIER_PREFIXES,
    CLASSIFY_FIELD_TAGS,
    classifier_tags,
    merge_tags,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeErrorResponse:
    """Mimics an httpx.Response whose raise_for_status() raises for status_code."""

    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self) -> None:
        raise httpx.HTTPStatusError("error", request=None, response=self)


class TestClassifierTags:
    def test_namespaces_all_three_fields(self):
        result = {
            "category": "procurement",
            "operational_domain": "air",
            "region": "americas",
        }
        assert classifier_tags(result) == [
            "category:procurement",
            "domain:air",
            "region:americas",
        ]

    def test_skips_missing_fields(self):
        assert classifier_tags({"category": "policy"}) == ["category:policy"]
        assert classifier_tags({}) == []

    def test_ignores_empty_strings(self):
        assert classifier_tags({"category": "", "operational_domain": "sea"}) == [
            "domain:sea"
        ]

    def test_ignores_unmapped_provider_fields(self):
        """An unadopted provider field is dropped, not fatal.

        This tolerance is why the v3.0.0 `region` addition did not break this
        service — and also why it went unnoticed. The cross-repo contract check
        is what makes such an addition loud; this function stays forgiving.
        """
        result = {
            "category": "policy",
            "operational_domain": "cyber",
            "region": "europe",
            "confidence": "0.91",
        }
        assert classifier_tags(result) == [
            "category:policy",
            "domain:cyber",
            "region:europe",
        ]


class TestClassifierPrefixesStayDerived:
    """`CLASSIFIER_PREFIXES` must cover every namespace `classifier_tags` emits.

    If a namespace is added to CLASSIFY_FIELD_TAGS but missed in the prefix list,
    `merge_tags` stops recognising those tags as its own, treats them as user
    tags, and reprocessing accumulates duplicates instead of converging —
    silently breaking the idempotency SYS-005 freezes. Deriving one from the
    other makes that impossible; this test pins the invariant so a future edit
    cannot quietly un-derive it.
    """

    def test_every_emitted_namespace_is_a_known_prefix(self):
        emitted = classifier_tags({field: "x" for field in CLASSIFY_FIELD_TAGS})
        for tag in emitted:
            assert tag.startswith(CLASSIFIER_PREFIXES), (
                f"{tag!r} is not covered by CLASSIFIER_PREFIXES; reprocessing "
                f"would accumulate it instead of replacing it."
            )

    def test_region_tags_are_replaced_not_accumulated(self):
        """The concrete regression the derivation prevents."""
        result = {
            "category": "operations",
            "operational_domain": "air",
            "region": "middle-east",
        }
        first = classifier_tags(result)
        # Reprocess the same note: the region label changes upstream.
        result_v2 = {**result, "region": "europe"}
        merged = merge_tags(["mine", *first], classifier_tags(result_v2))
        assert "mine" in merged
        assert merged.count("region:middle-east") == 0
        assert merged.count("region:europe") == 1


class TestMergeTags:
    def test_preserves_user_tags(self):
        merged = merge_tags(["urgent", "review"], ["category:policy", "domain:cyber"])
        assert "urgent" in merged
        assert "review" in merged
        assert "category:policy" in merged
        assert "domain:cyber" in merged

    def test_replaces_stale_classifier_tags_not_accumulate(self):
        # A note already classified once; reprocessing yields different labels.
        existing = ["urgent", "category:operations", "domain:land"]
        merged = merge_tags(existing, ["category:procurement", "domain:air"])
        # Old classifier tags gone, new ones present, user tag kept.
        assert merged == ["urgent", "category:procurement", "domain:air"]
        assert "category:operations" not in merged
        assert "domain:land" not in merged

    def test_idempotent_on_identical_reprocess(self):
        existing = ["mine", "category:policy", "domain:cyber"]
        merged = merge_tags(existing, ["category:policy", "domain:cyber"])
        assert merged == ["mine", "category:policy", "domain:cyber"]

    def test_caps_at_20_classifier_tags_always_land(self):
        user_tags = [f"u{i}" for i in range(25)]
        merged = merge_tags(user_tags, ["category:policy", "domain:cyber"])
        assert len(merged) == 20
        # Classifier tags always present.
        assert "category:policy" in merged
        assert "domain:cyber" in merged
        # 18 most-recent user tags kept; oldest dropped.
        assert "u24" in merged
        assert "u0" not in merged

    def test_empty_existing(self):
        assert merge_tags([], ["category:industry", "domain:space"]) == [
            "category:industry",
            "domain:space",
        ]


class TestClassifyAndWriteback:
    def test_writes_namespaced_tags_and_sets_done(self, monkeypatch, session_factory):
        # Seed a note with a user tag.
        seed = session_factory()
        note = Note(title="Budget", content="Senate approves cyber budget")
        note.tags = ["mine"]
        seed.add(note)
        seed.commit()
        seed.refresh(note)
        note_id = note.id
        seed.close()

        calls = []
        sleeps = []

        def _post(*a, **k):
            calls.append(1)
            return _FakeResponse(
                {"category": "procurement", "operational_domain": "cyber"}
            )

        monkeypatch.setattr(tasks.httpx, "post", _post)
        monkeypatch.setattr(tasks.time, "sleep", lambda seconds: sleeps.append(seconds))
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        tasks.classify_and_writeback(note_id, "Senate approves cyber budget")

        # A first-attempt success should never retry or back off.
        assert len(calls) == 1
        assert sleeps == []
        check = session_factory()
        refreshed = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert set(refreshed.tags) == {"mine", "category:procurement", "domain:cyber"}
        assert refreshed.enrichment_status == "done"

    def test_noop_when_classifier_url_unset(self, monkeypatch):
        monkeypatch.delenv("CLASSIFIER_URL", raising=False)

        def _boom(*a, **k):
            raise AssertionError("classifier should not be called when URL is unset")

        monkeypatch.setattr(tasks.httpx, "post", _boom)
        # Must return cleanly without touching the classifier or the DB.
        tasks.classify_and_writeback(999, "some text")

    def test_noop_leaves_status_pending(self, monkeypatch, session_factory):
        """When CLASSIFIER_URL is unset, enrichment_status stays pending."""
        seed = session_factory()
        note = Note(title="t", content="c")
        note.tags = []
        seed.add(note)
        seed.commit()
        seed.refresh(note)
        note_id = note.id
        seed.close()

        monkeypatch.delenv("CLASSIFIER_URL", raising=False)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        tasks.classify_and_writeback(note_id, "c")

        check = session_factory()
        refreshed = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert refreshed.enrichment_status == "pending"

    def test_classifier_failure_sets_failed_status(self, monkeypatch, session_factory):
        seed = session_factory()
        note = Note(title="t", content="c")
        note.tags = ["keep"]
        seed.add(note)
        seed.commit()
        seed.refresh(note)
        note_id = note.id
        seed.close()

        calls = []

        def _raise(*a, **k):
            calls.append(1)
            raise RuntimeError("classifier down")

        monkeypatch.setattr(tasks.httpx, "post", _raise)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        # Should not raise; the note keeps its original tags.
        tasks.classify_and_writeback(note_id, "c")

        # A non-httpx exception (e.g. malformed JSON) isn't a network-retry
        # case — fails fast rather than burning the retry budget.
        assert len(calls) == 1
        check = session_factory()
        refreshed = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert list(refreshed.tags) == ["keep"]
        assert refreshed.enrichment_status == "failed"


class TestClassifyAndWritebackRetry:
    """SYS-013: retry transient classifier failures with backoff.

    Fails fast on anything that retrying the same request body can't fix.
    """

    def test_retries_transient_errors_then_succeeds(self, monkeypatch, session_factory):
        seed = session_factory()
        note = Note(title="t", content="c")
        note.tags = []
        seed.add(note)
        seed.commit()
        seed.refresh(note)
        note_id = note.id
        seed.close()

        calls = []

        def _flaky(*a, **k):
            calls.append(1)
            if len(calls) < 3:
                raise httpx.ConnectError("connection refused")
            return _FakeResponse({"category": "policy", "operational_domain": "cyber"})

        monkeypatch.setattr(tasks.httpx, "post", _flaky)
        monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        tasks.classify_and_writeback(note_id, "c")

        assert len(calls) == 3  # failed twice, succeeded on the 3rd attempt
        check = session_factory()
        refreshed = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert refreshed.enrichment_status == "done"
        assert set(refreshed.tags) == {"category:policy", "domain:cyber"}

    def test_exhausts_retries_on_persistent_5xx_and_logs_warning(
        self, monkeypatch, session_factory, caplog
    ):
        seed = session_factory()
        note = Note(title="t", content="c")
        note.tags = ["keep"]
        seed.add(note)
        seed.commit()
        seed.refresh(note)
        note_id = note.id
        seed.close()

        calls = []

        def _always_503(*a, **k):
            calls.append(1)
            return _FakeErrorResponse(503)

        monkeypatch.setattr(tasks.httpx, "post", _always_503)
        monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        with caplog.at_level(logging.WARNING, logger="notes_api.tasks"):
            tasks.classify_and_writeback(note_id, "c")

        # Visibility signal (SYS-013): exhaustion is grep-able by note id and
        # names the attempt count, not just "it failed."
        assert len(calls) == tasks.MAX_ATTEMPTS
        assert any(
            str(note_id) in rec.message and "3 attempt" in rec.message
            for rec in caplog.records
        )
        check = session_factory()
        refreshed = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert refreshed.enrichment_status == "failed"
        assert list(refreshed.tags) == ["keep"]

    def test_client_error_does_not_retry(self, monkeypatch, session_factory):
        seed = session_factory()
        note = Note(title="t", content="c")
        note.tags = []
        seed.add(note)
        seed.commit()
        seed.refresh(note)
        note_id = note.id
        seed.close()

        calls = []

        def _always_422(*a, **k):
            calls.append(1)
            return _FakeErrorResponse(422)

        monkeypatch.setattr(tasks.httpx, "post", _always_422)
        monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        tasks.classify_and_writeback(note_id, "c")

        assert len(calls) == 1  # a 4xx won't succeed on retry
        check = session_factory()
        refreshed = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert refreshed.enrichment_status == "failed"
