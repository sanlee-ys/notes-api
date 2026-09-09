# ADR-003: Durable enrichment outbox in SQLite

**Status:** Accepted
**Date:** 2026-09-09
**Deciders:** San Lee

---

## Context

`POST /notes` enriches a new note through the classifier (SYS-005). ADR-001 dropped
Kafka because a broker is not justified at single-user scale. The write path then
used FastAPI `BackgroundTasks` as the only queue.

That path is not durable. The 201 response commits the note. The task then lives
only in process memory. A process crash after 201 drops the enrichment. SYS-013
retry lives inside `classify_and_writeback` and does not survive a crash.

Architecture Later names the upgrade as "Celery + Redis or outbox". Celery adds a
broker. That is the same class of cost ADR-001 refused. The outbox keeps the work
in SQLite, which this service already runs.

## Decision

Store each enrichment as an `EnrichmentJob` row in SQLite. Insert that row in the
same commit as the note. Drain due jobs in process. Do not add Celery or Redis.

- Status values are `queued`, `running`, `done`, and `failed`.
- `POST /notes` inserts a `queued` job and then kicks `process_due_jobs` through
  `BackgroundTasks`, so Starlette TestClient still runs the work after the
  response.
- `process_due_jobs` claims due `queued` jobs and crashed `running` jobs, calls
  the existing `classify_and_writeback`, and marks the job `done` or `failed`.
  Classifier retry and backoff stay in `tasks.py` (SYS-013). Namespaced tag
  replace is unchanged (SYS-005).
- On startup the lifespan resets stale `running` rows to `queued`, then starts a
  small asyncio loop that calls `process_due_jobs` on a timer. Shutdown cancels
  the loop.
- When `CLASSIFIER_URL` is unset, the job stays `queued` and
  `note.enrichment_status` stays `pending`. That is not a failure.

The HTTP router and the SYS-006 read contract do not change.

## Consequences

- **What this makes easier.** A process restart does not drop a queued
  enrichment. The service still runs with SQLite and no extra process.
- **What it costs.** The worker is still one process. A long outage of the
  classifier leaves jobs `queued` until `CLASSIFIER_URL` is set and the loop
  drains them. There is no separate replay tool.
- **What it forecloses / revisit triggers.** The no-Kafka decision in ADR-001
  still holds. Revisit only if this service needs fan-out to more than one
  consumer, or a worker fleet that SQLite cannot serve.

## Alternatives Considered

| Option | Reason Not Chosen |
|--------|-------------------|
| Keep BackgroundTasks as the only queue | A crash after 201 still drops the job. That is the gap this ADR closes. |
| Celery + Redis | Adds a broker. ADR-001 already refused that cost at this scale. |
| Kafka / NATS | Same broker cost. ADR-001 dropped Kafka on purpose. |
| Synchronous classify on POST | Couples note creation to the classifier. A down classifier fails the write. |

## Downstream surfaces

- `src/notes_api/models.py` — `EnrichmentJob` table, created with
  `Base.metadata.create_all`.
- `src/notes_api/service.py` — `create` inserts the job in the same commit as
  the note.
- `src/notes_api/tasks.py` — `recover_stale_jobs`, `process_due_jobs`;
  `classify_and_writeback` stays callable for existing tests.
- `src/notes_api/router.py` — POST kicks `process_due_jobs`; path list and
  response shapes stay the same.
- `src/notes_api/main.py` — lifespan recover plus the poll loop.
- `tests/test_outbox.py` — crash recovery and `CLASSIFIER_URL` unset.
- `contracts/otel-spans.json` — required span names for an enrichment run.
- `Dockerfile`, `.github/workflows/docker.yml` — serving image and `/health`
  smoke.
- `CLAUDE.md`, `README.md` — operator and agent text for the outbox.
- `decisions/ADR-001-classify-writeback-backgroundtasks.md` — dated line that
  the "no retry / no replay" cost is closed here. The no-Kafka decision stays.
- architecture `SYS-005` and `program/README.md` — other repo; not changed in
  this pull request.
