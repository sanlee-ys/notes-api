"""Tests for the durable enrichment outbox (ADR-003)."""

from datetime import datetime, timezone

from notes_api import tasks
from notes_api.models import EnrichmentJob, Note


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _seed_note_and_job(session_factory, *, status="queued", attempts=0, tags=None):
    seed = session_factory()
    note = Note(title="Budget", content="Senate approves cyber budget")
    note.tags = list(tags or ["mine"])
    seed.add(note)
    seed.flush()
    job = EnrichmentJob(
        note_id=note.id,
        payload_text=f"{note.title}\n{note.content}",
        status=status,
        attempts=attempts,
        available_at=datetime.now(timezone.utc),
    )
    seed.add(job)
    seed.commit()
    seed.refresh(note)
    seed.refresh(job)
    note_id = note.id
    job_id = job.id
    seed.close()
    return note_id, job_id


def _patch_classifier(monkeypatch, session_factory, payload=None):
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")
    monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)
    body = payload or {
        "category": "procurement",
        "operational_domain": "cyber",
    }
    monkeypatch.setattr(tasks.httpx, "post", lambda *a, **k: _FakeResponse(body))


class TestCreateEnqueuesJob:
    def test_post_inserts_queued_job_in_same_commit(self, client, db):
        body = client.post(
            "/notes", json={"title": "Cyber budget", "content": "Senate hearing"}
        ).json()
        jobs = db.query(EnrichmentJob).all()
        assert len(jobs) == 1
        assert jobs[0].note_id == body["id"]
        assert jobs[0].status == "queued"
        assert jobs[0].attempts == 0
        assert jobs[0].payload_text == "Cyber budget\nSenate hearing"
        assert body["enrichment_status"] == "pending"

    def test_delete_note_removes_outbox_row(self, client, db):
        body = client.post("/notes", json={"title": "t", "content": "c"}).json()
        assert db.query(EnrichmentJob).count() == 1
        client.delete(f"/notes/{body['id']}")
        assert db.query(Note).filter(Note.id == body["id"]).first() is None
        assert db.query(EnrichmentJob).count() == 0


class TestClassifierUrlUnset:
    def test_process_leaves_job_queued_and_note_pending(
        self, monkeypatch, session_factory
    ):
        note_id, job_id = _seed_note_and_job(session_factory)
        monkeypatch.delenv("CLASSIFIER_URL", raising=False)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)

        assert tasks.process_due_jobs() == 0

        check = session_factory()
        note = check.query(Note).filter(Note.id == note_id).first()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        check.close()
        assert note.enrichment_status == "pending"
        assert list(note.tags) == ["mine"]
        assert job.status == "queued"
        assert job.attempts == 0


class TestCrashRecovery:
    def test_running_job_recovers_and_completes(self, monkeypatch, session_factory):
        """A job left ``running`` after a crash is requeued and then done.

        This is the durability claim: a process restart must not drop work that
        was already committed as an outbox row.
        """
        note_id, job_id = _seed_note_and_job(
            session_factory, status="running", attempts=1
        )
        _patch_classifier(monkeypatch, session_factory)

        recovered = tasks.recover_stale_jobs()
        processed = tasks.process_due_jobs()

        assert recovered == 1
        assert processed == 1
        check = session_factory()
        note = check.query(Note).filter(Note.id == note_id).first()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        check.close()
        assert set(note.tags) == {"mine", "category:procurement", "domain:cyber"}
        assert note.enrichment_status == "done"
        assert job.status == "done"
        assert job.last_error is None

    def test_process_claims_due_running_job_without_recover(
        self, monkeypatch, session_factory
    ):
        note_id, job_id = _seed_note_and_job(
            session_factory, status="running", attempts=1
        )
        _patch_classifier(monkeypatch, session_factory)

        assert tasks.process_due_jobs() == 1

        check = session_factory()
        note = check.query(Note).filter(Note.id == note_id).first()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        check.close()
        assert note.enrichment_status == "done"
        assert job.status == "done"

    def test_recover_with_no_running_jobs_is_zero(self, monkeypatch, session_factory):
        _seed_note_and_job(session_factory, status="queued")
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        assert tasks.recover_stale_jobs() == 0


class TestProcessDueJobs:
    def test_success_marks_job_done_and_writes_tags(self, monkeypatch, session_factory):
        note_id, job_id = _seed_note_and_job(session_factory)
        _patch_classifier(monkeypatch, session_factory)

        assert tasks.process_due_jobs() == 1

        check = session_factory()
        note = check.query(Note).filter(Note.id == note_id).first()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        check.close()
        assert note.enrichment_status == "done"
        assert "category:procurement" in note.tags
        assert job.status == "done"

    def test_classifier_failure_marks_job_failed(self, monkeypatch, session_factory):
        note_id, job_id = _seed_note_and_job(session_factory)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")
        monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)

        def _raise(*a, **k):
            raise RuntimeError("classifier down")

        monkeypatch.setattr(tasks.httpx, "post", _raise)

        assert tasks.process_due_jobs() == 1

        check = session_factory()
        note = check.query(Note).filter(Note.id == note_id).first()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        check.close()
        assert note.enrichment_status == "failed"
        assert list(note.tags) == ["mine"]
        assert job.status == "failed"
        assert job.last_error == "classifier enrichment failed"

    def test_limit_caps_how_many_jobs_are_claimed(self, monkeypatch, session_factory):
        _seed_note_and_job(session_factory)
        _seed_note_and_job(session_factory)
        _patch_classifier(monkeypatch, session_factory)

        assert tasks.process_due_jobs(limit=1) == 1
        check = session_factory()
        statuses = [j.status for j in check.query(EnrichmentJob).all()]
        check.close()
        assert statuses.count("done") == 1
        assert statuses.count("queued") == 1

    def test_http_kick_processes_job_after_create(
        self, client, db, monkeypatch, session_factory
    ):
        _patch_classifier(monkeypatch, session_factory)

        body = client.post(
            "/notes",
            json={"title": "Budget", "content": "Senate approves cyber budget"},
        ).json()
        db.expire_all()
        note = db.query(Note).filter(Note.id == body["id"]).first()
        job = (
            db.query(EnrichmentJob).filter(EnrichmentJob.note_id == body["id"]).first()
        )
        assert note.enrichment_status == "done"
        assert "category:procurement" in note.tags
        assert job.status == "done"

    def test_missing_job_after_claim_is_a_noop(self, monkeypatch, session_factory):
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        tasks._run_claimed_job(9999)

    def test_no_due_jobs_returns_zero(self, monkeypatch, session_factory):
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")
        assert tasks.process_due_jobs() == 0

    def test_job_deleted_during_classify_is_a_noop(self, monkeypatch, session_factory):
        _seed_note_and_job(session_factory)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        def _delete_job(note_id: int, text: str) -> None:
            db = session_factory()
            db.query(EnrichmentJob).delete()
            db.commit()
            db.close()

        monkeypatch.setattr(tasks, "classify_and_writeback", _delete_job)
        assert tasks.process_due_jobs() == 1
        check = session_factory()
        assert check.query(EnrichmentJob).count() == 0
        check.close()

    def test_pending_writeback_requeues_job(self, monkeypatch, session_factory):
        """Do not mark failed when classify leaves the note pending."""
        note_id, job_id = _seed_note_and_job(session_factory)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")
        monkeypatch.setattr(tasks, "classify_and_writeback", lambda *a, **k: None)

        assert tasks.process_due_jobs() == 1

        check = session_factory()
        note = check.query(Note).filter(Note.id == note_id).first()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        check.close()
        assert note.enrichment_status == "pending"
        assert job.status == "queued"

    def test_recover_swallows_db_errors(self, monkeypatch):
        class _Boom:
            def query(self, *a, **k):
                raise RuntimeError("db down")

            def rollback(self) -> None:
                return None

            def close(self) -> None:
                return None

        monkeypatch.setattr(tasks, "SessionLocal", lambda: _Boom())
        assert tasks.recover_stale_jobs() == 0

    def test_claim_swallows_db_errors(self, monkeypatch):
        class _Boom:
            def query(self, *a, **k):
                raise RuntimeError("db down")

            def rollback(self) -> None:
                return None

            def close(self) -> None:
                return None

        monkeypatch.setattr(tasks, "SessionLocal", lambda: _Boom())
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")
        assert tasks.process_due_jobs() == 0

    def test_outcome_commit_failure_is_swallowed(self, monkeypatch, session_factory):
        note_id, job_id = _seed_note_and_job(session_factory)
        _patch_classifier(monkeypatch, session_factory)
        real_factory = session_factory
        commits = {"n": 0}

        def _factory():
            session = real_factory()
            original = session.commit

            def _commit() -> None:
                commits["n"] += 1
                # Claim commit is first; outcome commit is later.
                if commits["n"] >= 3:
                    raise RuntimeError("database went away")
                original()

            session.commit = _commit  # type: ignore[method-assign]
            return session

        monkeypatch.setattr(tasks, "SessionLocal", _factory)
        assert tasks.process_due_jobs() == 1

    def test_classify_raise_marks_job_failed(self, monkeypatch, session_factory):
        note_id, job_id = _seed_note_and_job(session_factory)
        monkeypatch.setattr(tasks, "SessionLocal", session_factory)
        monkeypatch.setenv("CLASSIFIER_URL", "http://fake-classifier")

        def _boom(note_id, text):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(tasks, "classify_and_writeback", _boom)
        assert tasks.process_due_jobs() == 1

        check = session_factory()
        job = check.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        note = check.query(Note).filter(Note.id == note_id).first()
        check.close()
        assert job.status == "failed"
        assert "unexpected" in (job.last_error or "")
        assert note.enrichment_status == "pending"


class TestOutboxLoop:
    def test_loop_stops_when_event_is_set(self, monkeypatch):
        import asyncio

        from notes_api import main

        calls: list[int] = []
        monkeypatch.setattr(main, "process_due_jobs", lambda: calls.append(1))
        monkeypatch.setattr(main, "OUTBOX_POLL_SECONDS", 0.01)

        async def _run() -> None:
            stop = asyncio.Event()
            task = asyncio.create_task(main._run_outbox_loop(stop))
            await asyncio.sleep(0.05)
            stop.set()
            await asyncio.wait_for(task, timeout=1)

        asyncio.run(_run())
        assert calls

    def test_loop_survives_a_poll_exception(self, monkeypatch):
        import asyncio

        from notes_api import main

        calls: list[int] = []

        def _flaky() -> None:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("poll failed")

        monkeypatch.setattr(main, "process_due_jobs", _flaky)
        monkeypatch.setattr(main, "OUTBOX_POLL_SECONDS", 0.01)

        async def _run() -> None:
            stop = asyncio.Event()
            task = asyncio.create_task(main._run_outbox_loop(stop))
            await asyncio.sleep(0.05)
            stop.set()
            await asyncio.wait_for(task, timeout=1)

        asyncio.run(_run())
        assert len(calls) >= 2
