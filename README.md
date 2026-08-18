# notes-api

![CI](https://github.com/sanlee-ys/notes-api/actions/workflows/ci.yml/badge.svg)

A personal Notes REST API in Python / FastAPI. Notes take optional tags.
Search is a case-insensitive substring. After a note is saved, an optional
background call to `defense-news-classifier` writes namespaced tags:
`category:…`, `domain:…` (from `operational_domain`), and `region:…`.

First written in Java/Spring Boot. See `decisions/ADR-001`.

## Tech stack

- **Python 3.11+**
- **FastAPI:** HTTP layer, dependency injection, BackgroundTasks
- **SQLAlchemy 2.x:** ORM. Tables: `notes` and `note_tags`.
- **SQLite** (default, file `notes.db`) or **PostgreSQL** (set `DATABASE_URL`)
- **Pydantic v2:** request and response validation
- **uv:** dependency management (`pyproject.toml` + `uv.lock`)

## Architecture

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/architecture-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/architecture-light.svg">
    <img alt="notes-api architecture: HTTP → router → service → models → SQLite/Postgres, with BackgroundTasks enrichment to classifier (CLASSIFIER_URL)" src="images/architecture-dark.svg" width="920">
  </picture>
</p>

```
HTTP → router.py → service.py → models.py → SQLite / PostgreSQL
                 ↘ BackgroundTasks → classifier (CLASSIFIER_URL, optional)
```

- **`router.py`:** FastAPI router on `/notes`. Wires BackgroundTasks after POST.
- **`service.py`:** business logic. Raises `HTTPException` on 404/conflict.
- **`models.py`:** `Note` + `NoteTag` ORM entities. `tags` is a list property.
- **`schemas.py`:** Pydantic `NoteRequest`, `TagsRequest`, `NoteResponse`.
- **`database.py`:** engine + session factory. `DATABASE_URL` env var.

## Running it

```bash
uv sync                                                       # install deps
uvicorn notes_api.main:app --host ${HOST:-127.0.0.1} --port 8081   # start the server
```

The API listens on `http://localhost:8081`. Loopback is the default
(`decisions/ADR-002`). Set `HOST=0.0.0.0` only for a separate, secured
deployment. Data persists to `notes.db` in the working directory. Set
`DATABASE_URL` for PostgreSQL:

```bash
DATABASE_URL=postgresql://user:pass@localhost/notesdb \
  uvicorn notes_api.main:app --host ${HOST:-127.0.0.1} --port 8081
```

Set `CLASSIFIER_URL` to enable automatic tag enrichment after note creation:

```bash
CLASSIFIER_URL=http://localhost:8000 \
  uvicorn notes_api.main:app --host ${HOST:-127.0.0.1} --port 8081
```

If `CLASSIFIER_URL` is unset, classification is skipped.

## API

| Method | Path               | Body           | Status | Notes                                            |
|--------|--------------------|----------------|--------|--------------------------------------------------|
| GET    | `/notes`           |                | 200    | List notes; optional `?q=` text, `?tag=`, and `?published_after=`/`?published_before=` (ISO date) filters |
| GET    | `/notes/{id}`      |                | 200    | 404 if not found                                 |
| POST   | `/notes`           | `NoteRequest`  | 201    | 400/422 if title/content blank or invalid        |
| PUT    | `/notes/{id}`      | `NoteRequest`  | 200    | 404 if not found                                 |
| PUT    | `/notes/{id}/tags` | `TagsRequest`  | 200    | Replace tags (idempotent writeback; `SYS-005`)   |
| DELETE | `/notes/{id}`      |                | 204    | 404 if not found                                 |

`NoteRequest`: `{ "title": "...", "content": "...", "tags": ["..."], "published_at": "2014-03-15" }`.
`tags` and `published_at` are optional. `published_at` is the article date
(ISO 8601). Date-range filters use it. The server sets `id`, `created_at`,
`updated_at`, and `enrichment_status`.

### Example

```bash
curl -s -X POST http://localhost:8081/notes \
  -H "Content-Type: application/json" \
  -d '{"title":"Cyber budget hearing","content":"Senate Armed Services Committee approved..."}'
# → 201 {"id":1,"title":"...","content":"...","tags":[],"enrichment_status":"pending","published_at":null,"created_at":"...","updated_at":"..."}
```

## Testing

```bash
uv sync --group dev
uv run pytest                         # run tests (in-memory SQLite, no API key needed)
uv run pytest --cov=notes_api         # with coverage
uv run ruff check src/ tests/         # lint
uv run black --check src/ tests/      # format check
uv run mypy src/                      # type check
```

Tests run offline. They need no `CLASSIFIER_URL` and no `DATABASE_URL`.
