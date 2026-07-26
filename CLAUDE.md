# CLAUDE.md

Guidance for AI agents working in this repo.

## What this is, and who depends on it

A personal Notes REST API (Python/FastAPI, SQLAlchemy, uv). It is not a leaf project:
`kb-agent`'s `search_notes` tool reads `GET /notes` live, so **the read shape is a
frozen cross-repo contract** — [`contracts/notes-read.schema.json`](contracts/notes-read.schema.json),
frozen in architecture [`SYS-006`](https://github.com/sanlee-ys/architecture/blob/main/decisions/SYS-006-notes-read-contract.md).
Changing or removing a field there breaks a consumer in another repo; that's an ADR,
not a refactor.

The classify writeback is in-process `BackgroundTasks`, not a queue — Kafka was dropped
([`decisions/ADR-001`](decisions/ADR-001-classify-writeback-backgroundtasks.md)), and
the trust boundary for that call is [`ADR-002`](decisions/ADR-002-local-service-trust-boundary.md).

```bash
uv run pytest                    # in-memory SQLite, no API key needed
uv run ruff check src/ tests/    # lint (black + mypy also gate CI)
```

<!-- shared:links-verify v1 -->
## Links — verify before sending (hard rule)

Links given in chat must resolve: **full `github.com/<owner>/<repo>/blob/<ref>/<path>` URLs only**, **verify the path exists on the ref before sending** (unverified → say so), and **branch links are perishable** (prefer `main` once merged). Full rule + rationale: [claude-ops `conventions/links-verify.md`](https://github.com/sanlee-ys/claude-ops/blob/main/conventions/links-verify.md).
<!-- /shared:links-verify -->
