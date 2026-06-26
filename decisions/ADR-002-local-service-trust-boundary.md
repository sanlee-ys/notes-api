# ADR-002: Treat notes-api as a single-user local service; bind to localhost instead of adding auth

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** San Lee

---

## Context

A security review flagged that every `/notes` endpoint is unauthenticated: anyone who can
reach the port gets full CRUD over all notes, and there is no per-user ownership model. It
also flagged that the `spring-boot-h2console` dependency shipped at runtime scope, so a single
property could turn on an unauthenticated database console.

The real question is the **deployment context**, because that sets the severity. In this
system, `notes-api` is a personal, single-user service: the only client is the `kb-agent`,
which calls it over `http://localhost:8081` (see kb-agent `agent/tools.py`, `search_notes`).
There is no multi-user requirement (the classifier project's CLAUDE.md explicitly lists "auth,
multi-user features" as out of scope for the family). Adding real authentication would mean
inventing a credential, storing it in two repos, and updating the kb-agent seam to send it —
real cost and a new secret to manage — to protect a service that should never be on a network
in the first place.

## Decision

Harden by **shrinking the attack surface and documenting the trust boundary**, rather than
adding authentication:

- **Bind to loopback by default.** `server.address=${SERVER_ADDRESS:127.0.0.1}` — running the
  app no longer exposes it on the network. A deliberate, separately-secured deployment can set
  `SERVER_ADDRESS`, but the safe default requires no thought.
- **Move `spring-boot-h2console` to `test` scope** and set `spring.h2.console.enabled=false`,
  so the console can never be enabled in a running app (belt and suspenders).
- **Don't leak internals in errors:** `server.error.include-stacktrace=never` and
  `server.error.include-message=never`, so Spring Boot's default error response stays generic
  (no class names, messages, or stack frames) without overriding the correct status codes —
  `NoteNotFoundException` still maps to 404, malformed input to 400, etc. (A blanket
  `@ExceptionHandler(Exception.class)` was considered and rejected: it would intercept those
  framework/`@ResponseStatus` exceptions and collapse 404/400/405 into 500.)
- **Record the trust boundary here**: notes-api is trusted-local, single-user, no authn/authz
  by design. Exposing it beyond loopback is out of contract without revisiting this ADR.

## Consequences

- **What this makes easier.** Running the service is safe by default; nothing to configure to
  avoid accidental network exposure. The kb-agent integration is unchanged (still loopback).
- **What it costs.** No authentication means the boundary *is* the network binding — if someone
  deliberately sets `SERVER_ADDRESS=0.0.0.0` without adding auth, the service is wide open. That
  risk is now explicit and owned, not silent.
- **What it forecloses / revisit triggers.** The moment notes-api needs to be reachable beyond
  the local machine, or gains a second (especially multi-user) client, this ADR must be
  superseded by one that adds real authentication (e.g. an API-key filter shared with the
  kb-agent seam) and, if multi-user, a per-note ownership model.

## Alternatives Considered

| Option | Reason Not Chosen |
|--------|-------------------|
| Add API-key / basic auth now | Real cost (a new shared secret across two repos + a coordinated kb-agent change) to protect a service that shouldn't be networked; over-engineering for a single-user local tool. Deferred to the revisit trigger above. |
| Add full Spring Security + per-user ownership | Multi-user is explicitly out of scope for this project family; large surface for no current need. |
| Leave H2 console at runtime scope, just disable via property | One property flip (or a profile) re-enables an unauthenticated DB console; test-scoping removes the dependency from the runtime classpath entirely — a stronger guarantee. |
| Do nothing (rely on "it's only local") | The trust boundary was undocumented and the default binding exposed it on all interfaces; an unwritten assumption isn't a control. |
