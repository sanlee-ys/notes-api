# ADR-001: Classify-writeback via FastAPI BackgroundTasks (supersedes Kafka approach)

**Status:** Current
**Date:** 2026-06-27
**Supersedes:** Kafka-based event-driven design (original v1 Java decision, 2026-06-21)

---

## Context

The notes-api POST /notes endpoint optionally enriches a newly-created note with
classification tags from the defense-news-classifier service (`category` +
`operational_domain`). The v1 Java implementation published a `NoteCreated` event to
a Kafka topic; the classifier consumed it and called back via `PUT /notes/{id}/tags`.

The service was ported from Java/Spring Boot to Python/FastAPI to reduce cognitive
overhead (maintaining Java + Python + ML simultaneously is too much parallel context
for a single-person portfolio). That port made the Kafka dependency an active liability:
a local Kafka KRaft cluster adds infrastructure cost with no benefit at single-user,
low-volume scale.

---

## Decision

Use **FastAPI `BackgroundTasks`** for the classify-writeback seam instead of a message
broker.

After `POST /notes` returns 201, the response is sent to the caller immediately. A
background task then calls `CLASSIFIER_URL/classify`, reads the structured response,
opens a **fresh `SessionLocal`** (the request's session is already closed by the time
the task runs), mutates `note.tags` directly on that fresh session, and commits. If
`CLASSIFIER_URL` is unset (the default in tests and local dev), the background task is
a no-op.

Errors in the classification call are swallowed — enrichment failure never surfaces to
the caller and never rolls back note creation.

---

## Consequences

**What this makes easier**
- Zero infrastructure dependencies: no Kafka, no ZooKeeper/KRaft, no consumer group.
- Local dev is `uvicorn notes_api.main:app --port 8081` with nothing else running.
- The API contract is identical to v1: same 6 endpoints, same request/response shapes.
  Callers (kb-agent's `search_notes`) are unaffected.

**What it costs**
- No at-least-once delivery. A transient classifier outage silently drops the enrichment
  for that note; there is no retry or dead-letter queue.
- No replay. If the classifier is upgraded and you want to re-classify existing notes,
  you re-POST or run a one-off script — there is no event log to consume.

**What it forecloses / revisit triggers**
This design is correct for a single-user local service. The revisit trigger is: if
notes-api ever needs durable enrichment guarantees, fan-out to multiple consumers, or
the ability to replay events, the right move is a proper message broker (Kafka or NATS).
At that scale, the infrastructure cost is justified.

---

## Historical note: why Kafka was chosen in v1

The original Java implementation deliberately used Kafka to demonstrate event-driven
architecture in a portfolio context — it was a portfolio signal, not a technical
requirement. `case-study/README.md` in the architecture repo called this out explicitly.
The Python port drops Kafka because the signal has been recorded (the Java source history
and the architecture case study both document it) and the ongoing carrying cost outweighs
the residual value.

---

## Alternatives Considered

| Option | Reason Not Chosen |
|--------|-------------------|
| Keep Kafka, rewrite consumer in Python | Same infrastructure cost; adds a kafka-python dependency to the classifier that isn't used for anything else in the portfolio |
| Synchronous inline call | Couples the services; note creation becomes as slow/fragile as the classifier and fails when it's down |
| Celery / Redis task queue | Adds a broker (Redis) — same class of problem as Kafka for this scale |
| BackgroundTasks (chosen) | No broker, same-process, zero infrastructure; fits the single-user local context |

---

## Amendments

> **Amendment (2026-07-05):** The Decision section originally described the
> writeback as patching tags "via the existing `set_tags` service call." That's
> not what shipped: the background task opens a **fresh `SessionLocal`**
> (the request's own DB session is already closed by the time the task runs),
> mutates `note.tags` directly on the note loaded from that fresh session, and
> commits — it does not call the `set_tags` service method. This doc has been
> corrected to match the shipped code. Docs follow code here, and a fresh
> session with a direct commit is the idiomatic pattern for FastAPI
> `BackgroundTasks` work that outlives the request's own session.

> **Amendment (2026-07-05):** The Consequences section originally stated
> "there is no retry or dead-letter queue." Per SYS-013 (self-healing by
> default, architecture repo), the classifier call now retries transient
> failures (connection errors, timeouts, 5xx) up to 3 attempts with backoff
> before writing `enrichment_status="failed"` and logging a WARNING with the
> note id and attempt count — so a recurring fault is observable rather than
> silently masked. This doesn't add a durable, cross-crash queue: retry is
> in-process only, so a worker crash mid-task still drops the enrichment for
> that note. The durable-queue revisit trigger above is unchanged — retry
> closes the "transient blip" gap, not the "worker died" one.
