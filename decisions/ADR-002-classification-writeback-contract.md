# ADR-002: Classification writeback via a dedicated PATCH endpoint with namespaced tags

**Status:** Accepted
**Date:** 2026-06-22
**Deciders:** San Lee

---

## Context

The event-driven classification loop (program *delivery plan* → product *spec* for the
event-driven classification loop) needs the classifier to write its result **back** onto a note
after it consumes a `NoteCreated` event. `ADR-001` opened the loop — notes-api now emits the event —
but nothing writes the classification back yet. **Gate 0** of the delivery plan ("verify the
dependency before building on it") inspected the existing seam and found it **unfit for a
side-channel writer**:

- **`PUT /notes/{id}` is a full replace.** It overwrites title, content, *and* tags in one shot
  (`NoteService.update`), and `NoteRequest` requires a **non-blank title and content** on every
  write. The classifier authors neither. To set tags through PUT it would read-modify-write the
  whole note — and if the user edited the note after creation, that PUT **reverts their edits** (a
  lost update). A classifier has no business being able to clobber the note body.
- **No place for typed output.** `Note` carries only a flat `Set<String> tags` (`Note.java:53`) —
  there is no `category` / `operationalDomain` field. The classifier produces two typed values; the
  model has one untyped bag.
- The **read side is already clean**: the fat `NoteCreated` event (id, title, content, tags) on
  `note-events` gives the classifier everything it needs to classify without a callback. Only the
  **write** side needs a contract.

The decision point: how does the classifier write its category + operational-domain back **safely
and idempotently** — notes-api delivers **at-least-once**, so the consumer may see an event twice
(risk **R1**, raised in `ADR-001` and the program risk register)?

## Decision

Add a **purpose-built, classification-scoped writeback endpoint**:

- **`PATCH /notes/{id}/classification`** — a partial update that touches *only* the classification,
  never title/content.
- The classifier's output is stored as **namespaced tags** in the existing `Note.tags` set — e.g.
  `category:<value>` and `domain:<value>` — alongside (not replacing) the user's plain tags.
- The write is an **upsert**: it **replaces** any existing `category:*` / `domain:*` tags with the
  new ones and leaves all non-namespaced (user) tags untouched. Applying the same classification
  twice produces the **identical** final state.
- **No event is published** on this writeback in v0. This avoids a `NoteCreated`→classify→writeback
  **feedback loop** and matches the current PUT-silent behavior. A `TagsUpdated` event is the future
  hook (see *revisit*).
- **No schema change.** It reuses the `note_tags` element collection and the existing tag search.

The load-bearing property: **idempotency is a property of the contract, not of the consumer.** "Set
this note's classification to X" is inherently idempotent, so redelivery is safe **without** a
consumer-side processed-events table. This is what lets **Gate 0 and Gate 1 (the R1 gate) collapse
into this one ADR**.

### Open knobs (pin during implementation; not blocking the contract)

- **Namespace syntax** — `category:` / `domain:` vs longer forms (`operational-domain:`). One
  canonical convention, honored by every writer and by the consumer.
- **Tag-budget interaction** — classification tags currently count against `NoteRequest`'s
  `@Size(max = 20)` limit. Decide whether to exempt namespaced tags or accept the small budget cost.
- **Stale-reclassification guard** — whether to pin a `classifier-version` so an older
  reclassification can't overwrite a newer one. Unneeded for the single-classifier v0; flagged for
  when models change.

## Consequences

- **What this makes easier.** The classifier writes **only its own concern** and physically *cannot*
  clobber the note body. Writeback is **idempotent**, so at-least-once redelivery is a non-event (R1
  retired at the contract level). Classification is immediately **queryable through the existing tag
  search** (e.g. `?tag=category:naval`) with no new query code and no migration.
- **What it costs (the tradeoff accepted).** Classification lives as **stringly-typed namespaced
  tags**, not first-class typed fields — so it isn't independently validated or strongly queryable
  the way columns would be, and every writer must respect the namespace convention. The writeback is
  **invisible to the event stream** in v0 (nothing downstream can react to a (re)classification yet).
  And classification tags **consume the 20-tag budget** unless exempted. Accepted for v0, documented
  here.
- **What we'll revisit.** When first-class querying, validation, or downstream reaction is needed,
  **promote** `category` / `operationalDomain` to **typed columns** (a schema migration) and **emit a
  `TagsUpdated` event** — a clean follow-up ADR. That supersedes the namespaced-tags representation,
  much as the transactional outbox is queued to supersede publish-in-service in `ADR-001`.

## Alternatives Considered

| Option | Reason Not Chosen |
|--------|-------------------|
| Reuse `PUT /notes/{id}` (read-modify-write) | Full replace requires resending title+content; a side-channel writer can clobber user edits (lost update), and idempotency stays fragile under redelivery + concurrent edits |
| `PATCH` + **structured typed fields** now (`category`/`operationalDomain` columns) | The cleaner long-term data model and more Spring/JPA migration practice — but a schema change is over-scoped for v0; recorded above as the revisit path |
| **Append** tags instead of upsert | Not idempotent: reprocessing or reclassifying accretes stale `category:*` tags, so the same event seen twice changes state |
| Consumer-side **processed-events table** for idempotency | Properly dedupes, but adds a table + bookkeeping the consumer must maintain — machinery this contract makes unnecessary, since the write is idempotent by construction |
| Emit an event on writeback in v0 | Creates a `NoteCreated`→classify→writeback feedback loop (or needs an event-type guard); deferred with the `TagsUpdated` hook until a consumer needs it |
