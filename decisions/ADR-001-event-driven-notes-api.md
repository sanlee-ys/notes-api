# ADR-001: Make notes-api event-driven by publishing NoteCreated

**Status:** Accepted
**Date:** 2026-06-21
**Deciders:** San Lee

---

## Context

`notes-api` was a synchronous CRUD REST service. The wider system needs the classifier to
react when a note is created — classify it, then write tags back. Doing that synchronously
(notes-api calling the classifier inline) would couple the two services, make note creation
as slow and as fragile as the classifier, and fail note creation outright when the classifier
is down. The system design (see `system/SYS-003` and the program dependency map) calls for the
classifier to **consume** note events. Relearning event-driven mechanics firsthand is also an
explicit goal of the project.

The decision point: how does `notes-api` emit a `NoteCreated` event, and with what consistency
guarantee between the database write and the Kafka publish?

## Decision

- Publish a **`NoteCreated`** domain event to Kafka whenever a note is created. Topic
  **`note-events`**, **keyed by the note id** (so per-note events stay ordered), value serialized
  as **JSON**.
- Publish from **`NoteService.create()`, immediately after `repository.save()` returns** — the
  "publish-in-service" approach. The save commits, then we send.
- **Fat event:** it carries the note's state (id, title, content, tags, createdAt) so the
  consumer can act without calling back for the content.
- **Client library:** Spring for Apache Kafka via `spring-boot-starter-kafka`, with Boot 4's
  Jackson 3 serializer (`JacksonJsonSerializer`).

## Consequences

- **What this makes easier.** Any consumer — the classifier first, later a search indexer or
  analytics — can subscribe to `note-events` without `notes-api` knowing it exists. Note creation
  stays fast and survives a classifier outage (the event waits durably in the log).
- **What it costs (the tradeoff accepted).** The **dual-write problem**: the DB commit and the
  Kafka send are two systems and are not atomic. A crash between them could leave a saved note
  with no event. For a single-instance local/learning setup this risk is small and **accepted**;
  it is documented here and in `NoteService.create()`'s Javadoc. It also introduces **eventual
  consistency** — a note's tags appear a moment after creation, not synchronously — and
  **at-least-once** delivery downstream, so consumers must be idempotent (risk R1).
- **What we'll revisit.** When moving to multiple instances / production, or when event loss
  becomes unacceptable, adopt the **transactional outbox** (write the event to an outbox table in
  the same DB transaction; a relay publishes to Kafka). That supersedes publish-in-service.

## Alternatives Considered

| Option | Reason Not Chosen |
|--------|-------------------|
| Synchronous call (notes-api calls the classifier inline) | Couples the services; note creation becomes as slow/fragile as the classifier and fails when it's down — defeats the purpose of an async seam |
| `@TransactionalEventListener(AFTER_COMMIT)` | Cleaner (never publishes for a rolled-back tx) and idiomatic, but more wiring and still not fully atomic; deferred as a reasonable mid-point upgrade |
| Transactional outbox | Properly solves the dual-write problem but needs an outbox table + relay/CDC; over-scoped for Phase 0 — recorded above as the production upgrade path |
| Spring Cloud Stream (binder abstraction) | Hides the Kafka mechanics being deliberately relearned (offsets, keys, delivery) |
| Avro + Schema Registry | Stronger schema guarantees but needs registry infrastructure; JSON is simpler, human-readable, and grader-friendly (consistent with `system/SYS-003`). Avro is the scale-up |
