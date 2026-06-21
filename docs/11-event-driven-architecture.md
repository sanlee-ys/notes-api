# Event-driven architecture

We just made `NoteService.create()` publish a `NoteCreated` event. That one line changed
what *kind* of system notes-api is — it's now event-driven, not just a synchronous REST
service. This note is the **why**: what event-driven architecture (EDA) is, what it buys,
and what it costs. (No free lunch — the costs are real and we name them.)

## The before: synchronous request/response

Until now, every interaction was **call-and-wait**:

```
client → POST /notes → NoteService → save to DB → return the note
```

Each step blocks on the next and you get an answer immediately. If we wanted the classifier
to tag a new note in this world, notes-api would have to **call the classifier and wait** for
it — which couples the two (notes-api now needs to know the classifier exists and be able to
reach it) and makes note creation as slow and as fragile as the classifier. If the classifier
is down, your `POST /notes` fails. In Python terms: a function that calls another function and
blocks on its return.

## The after: publish a fact, move on

Now `create()` saves the note and **publishes a `NoteCreated` event**, then returns straight
away:

```
client → POST /notes → NoteService → save to DB → publish NoteCreated → return
                                                         │
                                                         ▼
                                        (later) classifier reacts on its own time
```

notes-api doesn't know or care who consumes the event. Its job ends at *"I'm announcing that
a note was created."* Whoever's interested subscribes and reacts on their own schedule. The
analogy: instead of phoning the classifier directly, you drop a note in a mailbox and walk
away — anyone who cares picks it up.

If you've used **Celery** or a task queue in Python (publish a job, a worker handles it later),
this is the same shape. Kafka is the durable, replayable-log version of that idea.

## What it buys (the why)

- **Decoupling.** notes-api has no idea the classifier exists. You can add a *second* consumer
  later — a search indexer, analytics — **without touching notes-api at all**. Producers and
  consumers evolve independently.
- **Resilience.** If the classifier is down, note creation still works; the event sits in the
  log until the consumer catches up. A synchronous call would have failed.
- **Responsiveness.** The `POST` returns the instant the note is saved. The (possibly slow)
  classification happens asynchronously, off the request path.
- **Replayability.** The event log is durable and kept by offset (not deleted on read), so a
  brand-new consumer can read from the beginning — reprocess history, backfill a new feature.

## What it costs (the honest tradeoffs)

- **Eventual consistency.** The note exists immediately, but its classifier tags show up *a
  moment later*, once the consumer processes the event. The system is correct *eventually*,
  not instantly — and the UI/clients have to be OK with "the tag isn't there yet."
- **Harder to follow.** Synchronous code reads top-to-bottom. With events, the flow hops
  across services and time; you need **observability** (distributed tracing) to see the whole
  story. That's exactly why OpenTelemetry is on the roadmap.
- **The dual-write problem.** Saving to the DB and publishing to Kafka are two systems and
  aren't atomic. We chose the simple *publish-after-save* and accepted a small risk (a crash
  between the two could drop an event) — documented in the event-driven ADR; the **transactional
  outbox** is the production-grade fix.
- **At-least-once delivery.** A consumer may see the same event twice, so consumers must be
  **idempotent** (tracked as risk R1 — we'll handle it when we build the classifier consumer).

## Why we did it here

notes-api didn't *need* events to do CRUD — a plain REST API was fine. We made it event-driven
because the **system's design** calls for the classifier to react to new notes, and because
feeling these tradeoffs firsthand is the point of the exercise. The `NoteCreated` event is the
**seam** that lets the classifier (and any future consumer) plug in without notes-api ever
knowing they're there.

## Where it lives in the code

- `NoteService.create()` publishes the event after the save.
- The event: `src/main/java/com/notes/api/event/NoteCreated.java` (a JSON record).
- Topic `note-events`, keyed by the note id — see
  [Kafka: partitions & brokers](10-kafka-partitions-and-brokers.md) for why the key matters.
