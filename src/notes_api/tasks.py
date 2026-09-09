"""Background enrichment: classify a new note and write labels back as tags.

This implements the writeback half of the SYS-005 classify-and-writeback contract.
Jobs live in the SQLite outbox (``EnrichmentJob``, ADR-003) so a process crash
after ``POST /notes`` does not drop the work. FastAPI BackgroundTasks is only
the same-process kick that drains due jobs after the HTTP response; a small
asyncio loop in the app lifespan does the same drain on a timer. There is no
broker. The worker calls the classifier's HTTP `/classify` seam (SYS-004) and
writes the predicted labels back as namespaced tags with replace semantics so
reprocessing is idempotent (R1).

Enrichment status lifecycle:
  pending → done   (classifier returned labels and they were written back)
  pending → failed (classifier error, unreachable, or returned no labels)

When CLASSIFIER_URL is unset (dev/test), ``classify_and_writeback`` is a no-op
and ``process_due_jobs`` leaves the job ``queued``. Note status stays
"pending" — that signals "not configured" rather than "failed."

Per SYS-013 (self-healing by default), the classifier call retries transient
failures (connection errors, timeouts, 5xx) with backoff — a 4xx or any other
error shape is not retried, since the same request body would just fail again.
Exhausting retries (or any non-retryable failure) logs a WARNING with the note
id and attempt count, so a fault that keeps recurring is grep-able rather than
silently masked.
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import httpx

from .database import SessionLocal
from .models import EnrichmentJob, Note
from .service import NoteService
from .telemetry import get_tracer

logger = logging.getLogger(__name__)

# This consumer's belief about the frozen /classify response shape (SYS-004),
# and the tag namespace each field is encoded under. Kept in one place so the
# runtime encoder, the replace-semantics prefix list, and the cross-repo contract
# check cannot disagree — two copies of a shape drifting apart unnoticed is the
# exact failure SYS-018 exists to prevent.
#
# The rename operational_domain -> domain: is deliberate and part of the frozen
# encoding.
CLASSIFY_FIELD_TAGS: dict[str, str] = {
    "category": "category",
    "operational_domain": "domain",
    "region": "region",
}

# Classifier-owned tags are namespaced so the writeback can replace only its own
# prior tags on reprocessing, never a user's hand-applied tags (SYS-005).
#
# DERIVED, not hand-listed: if a namespace is added to CLASSIFY_FIELD_TAGS but
# missed here, merge_tags stops recognising those tags as its own, treats them as
# user tags, and reprocessing accumulates duplicates instead of converging —
# silently breaking the idempotency SYS-005 freezes. Deriving makes that
# impossible.
CLASSIFIER_PREFIXES = tuple(f"{ns}:" for ns in CLASSIFY_FIELD_TAGS.values())
TAG_CAP = 20

MAX_ATTEMPTS = 3
# Backoff after attempt 1 and attempt 2 respectively; matches the schedule in
# learning-notes' retry-with-backoff writeup.
RETRY_BACKOFF_SECONDS = (2, 4)

# Outbox drain: claim at most this many due jobs per kick or poll.
DEFAULT_JOB_LIMIT = 10
# Claim lease. A ``running`` row whose ``available_at`` is still in the future
# is in flight in this process; a due ``running`` row is a crash leftover.
CLAIM_LEASE_SECONDS = 60


def classifier_tags(result: dict[str, str]) -> list[str]:
    """Encode the classifier's response fields as namespaced tags.

    Reads only the fields in ``CLASSIFY_FIELD_TAGS``. A field the classifier
    sends that is not mapped here is ignored rather than fatal — that tolerance
    is why the v3.0.0 ``region`` addition did not break this service, and also
    why it went unnoticed for a day. The cross-repo contract check is what makes
    such an addition loud; this function stays forgiving on purpose.

    Args:
        result: The parsed ``/classify`` 200 body.

    Returns:
        Namespaced tags, in ``CLASSIFY_FIELD_TAGS`` order. Missing or empty
        fields are skipped so a partial response still enriches what it can.
    """
    tags: list[str] = []
    for field, namespace in CLASSIFY_FIELD_TAGS.items():
        value = result.get(field)
        if value:
            tags.append(f"{namespace}:{value}")
    return tags


def merge_tags(
    existing: list[str], new_classifier_tags: list[str], cap: int = TAG_CAP
) -> list[str]:
    """Merge fresh classifier tags into a note's existing tags (SYS-005).

    User tags are preserved; the task's own prior classifier tags (namespaced)
    are dropped and replaced — so reprocessing converges instead of accumulating.
    Capped at ``cap``: the classifier tags always land; the oldest user tags are
    dropped from this snapshot if the note is already at the cap.
    """
    user_tags = [t for t in existing if not t.startswith(CLASSIFIER_PREFIXES)]
    room = max(cap - len(new_classifier_tags), 0)
    kept_user = user_tags[-room:] if room else []
    return kept_user + new_classifier_tags


def _write_enrichment_status(note_id: int, status: str) -> None:
    """Persist enrichment_status on a note. Best-effort: never raises."""
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            note.enrichment_status = status
            db.commit()
    except Exception:
        logger.exception(
            "failed to persist enrichment_status=%s for note %s", status, note_id
        )
    finally:
        db.close()


def classify_and_writeback(note_id: int, text: str) -> None:
    """Classify ``text`` and write the labels back to note ``note_id``.

    No-op when ``CLASSIFIER_URL`` is unset (the default in dev/tests). Retries
    connection errors, timeouts, and 5xx responses up to MAX_ATTEMPTS times with
    backoff; a 4xx or any other error shape fails immediately since retrying the
    same body won't help. On exhaustion (or any non-retryable failure), writes
    ``enrichment_status="failed"`` and logs a WARNING so callers can see the
    enrichment didn't land. On success, writes the classifier tags back and sets
    ``enrichment_status="done"``.
    """
    classifier_url = os.getenv("CLASSIFIER_URL", "")
    if not classifier_url:
        return  # Not configured — leave status as "pending" (not a failure).

    # One span per enrichment task, with a child span per HTTP attempt so retries
    # of the cross-service /classify hop (SYS-004) are visible. A no-op unless
    # NOTES_API_TRACING is set (see telemetry.py), so tests/normal runs pay nothing.
    tracer = get_tracer()
    endpoint = f"{classifier_url}/classify"
    with tracer.start_as_current_span("classify_and_writeback") as task_span:
        task_span.set_attribute("notes_api.note_id", note_id)

        result: dict[str, str] | None = None
        last_exc: Exception | None = None
        attempts_made = 0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempts_made = attempt
            with tracer.start_as_current_span("POST /classify") as http_span:
                http_span.set_attribute("http.request.method", "POST")
                http_span.set_attribute("url.full", endpoint)
                http_span.set_attribute("notes_api.attempt", attempt)
                try:
                    resp = httpx.post(endpoint, json={"text": text}, timeout=10.0)
                    if http_span.is_recording():
                        http_span.set_attribute(
                            "http.response.status_code", resp.status_code
                        )
                    resp.raise_for_status()
                    result = resp.json()
                    break
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if http_span.is_recording():
                        http_span.set_attribute("error.type", type(exc).__name__)
                    if exc.response.status_code < 500:
                        break  # client error — retrying the same body won't help
                except httpx.HTTPError as exc:
                    last_exc = exc
                    if http_span.is_recording():
                        http_span.set_attribute("error.type", type(exc).__name__)
                except Exception as exc:
                    last_exc = exc
                    if http_span.is_recording():
                        http_span.set_attribute("error.type", type(exc).__name__)
                    break  # unexpected error shape — don't retry blindly

            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])

        task_span.set_attribute("notes_api.enrichment.attempts", attempts_made)

        if result is None:
            logger.warning(
                "classifier request failed for note %s after %d attempt(s): %r",
                note_id,
                attempts_made,
                last_exc,
            )
            task_span.set_attribute("notes_api.enrichment.status", "failed")
            _write_enrichment_status(note_id, "failed")
            return

        new_tags = classifier_tags(result)
        if not new_tags:
            logger.warning(
                "classifier returned no tags for note %s: %r", note_id, result
            )
            task_span.set_attribute("notes_api.enrichment.status", "failed")
            _write_enrichment_status(note_id, "failed")
            return

        # Fresh session: the request's session is closed once the response is sent.
        db = SessionLocal()
        try:
            service = NoteService(db)
            note = service.get_by_id(note_id)  # raises 404 if deleted pre-writeback
            merged = merge_tags(note.tags, new_tags)
            note.tags = merged
            note.enrichment_status = "done"
            db.commit()
            task_span.set_attribute("notes_api.enrichment.status", "done")
            logger.info("note %s classified; tags written back: %s", note_id, new_tags)
        except Exception:
            task_span.set_attribute("notes_api.enrichment.status", "writeback_skipped")
            logger.warning(
                "writeback skipped for note %s (likely deleted before writeback)",
                note_id,
            )
        finally:
            db.close()


def recover_stale_jobs() -> int:
    """Reset jobs left ``running`` after a process crash back to ``queued``.

    Startup calls this before the poll loop so a kill mid-claim does not leave
    work stuck. ``available_at`` is set to now so the next drain may claim them.

    Returns:
        The number of jobs reset.
    """
    db = SessionLocal()
    try:
        jobs = db.query(EnrichmentJob).filter(EnrichmentJob.status == "running").all()
        if not jobs:
            return 0
        now = datetime.now(timezone.utc)
        for job in jobs:
            job.status = "queued"
            job.available_at = now
        db.commit()
        logger.info("requeued %d stale enrichment job(s) after crash", len(jobs))
        return len(jobs)
    except Exception:
        logger.exception("failed to recover stale enrichment jobs")
        db.rollback()
        return 0
    finally:
        db.close()


def process_due_jobs(limit: int = DEFAULT_JOB_LIMIT) -> int:
    """Claim due outbox jobs and run ``classify_and_writeback`` for each.

    Due means ``available_at`` is now or past, and status is ``queued`` or
    crashed ``running``. When ``CLASSIFIER_URL`` is unset, this returns 0 and
    does not claim: jobs stay ``queued`` and note status stays ``pending``.

    Retry and backoff for the classifier hop stay inside
    ``classify_and_writeback`` (SYS-013). This function marks the job
    ``done`` or ``failed`` from the note's enrichment status.

    Args:
        limit: Maximum number of jobs to claim in this drain.

    Returns:
        The number of jobs claimed (and then run).
    """
    if not os.getenv("CLASSIFIER_URL", ""):
        return 0

    job_ids = _claim_due_jobs(limit)
    for job_id in job_ids:
        _run_claimed_job(job_id)
    return len(job_ids)


def _claim_due_jobs(limit: int) -> list[int]:
    """Mark due jobs ``running`` and return their ids."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        jobs = (
            db.query(EnrichmentJob)
            .filter(
                EnrichmentJob.status.in_(("queued", "running")),
                EnrichmentJob.available_at <= now,
            )
            .order_by(EnrichmentJob.created_at.asc())
            .limit(limit)
            .all()
        )
        if not jobs:
            return []
        lease_until = now + timedelta(seconds=CLAIM_LEASE_SECONDS)
        claimed: list[int] = []
        for job in jobs:
            job.status = "running"
            job.attempts += 1
            job.available_at = lease_until
            claimed.append(job.id)
        db.commit()
        return claimed
    except Exception:
        logger.exception("failed to claim due enrichment jobs")
        db.rollback()
        return []
    finally:
        db.close()


def _run_claimed_job(job_id: int) -> None:
    """Run classify-and-writeback for one claimed job and record the outcome."""
    db = SessionLocal()
    try:
        job = db.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        if job is None:
            return
        note_id = job.note_id
        text = job.payload_text
    finally:
        db.close()

    error: str | None = None
    try:
        classify_and_writeback(note_id, text)
    except Exception as exc:
        error = repr(exc)
        logger.exception("enrichment job %s raised", job_id)

    db = SessionLocal()
    try:
        job = db.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        if job is None:
            return
        if error is not None:
            job.status = "failed"
            job.last_error = error
            db.commit()
            return
        note = db.query(Note).filter(Note.id == job.note_id).first()
        if note is None or note.enrichment_status == "done":
            job.status = "done"
            job.last_error = None
        elif note.enrichment_status == "failed":
            job.status = "failed"
            if job.last_error is None:
                job.last_error = "classifier enrichment failed"
        else:
            # pending: classifier was not configured. Do not mark failed.
            job.status = "queued"
            job.available_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        logger.exception("failed to record outcome for enrichment job %s", job_id)
        db.rollback()
    finally:
        db.close()
