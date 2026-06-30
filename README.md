# notes-api

![CI](https://github.com/sanlee-ys/notes-api/actions/workflows/ci.yml/badge.svg)

A personal **Notes REST API** built with **Python / FastAPI**. It stores notes with
optional tags, supports case-insensitive substring search, and has an optional background enrichment
seam: after a note is saved, it calls the `defense-news-classifier` service and
writes the predicted `category` and `operational_domain` tags back to the note.

Previously written in Java/Spring Boot as a "get back into Java" exercise. Ported
to Python to match the rest of the portfolio stack and reduce cognitive load. The
Java history lives in this repo's git history; `decisions/ADR-001` documents the
architectural trade-off.

## Tech stack

- **Python 3.11+**
- **FastAPI** — HTTP layer, dependency injection, BackgroundTasks
- **SQLAlchemy 2.x** — ORM; `notes` + `note_tags` tables
- **SQLite** (default, file `notes.db`) or **PostgreSQL** (set `DATABASE_URL`)
- **Pydantic v2** — request/response validation
- **uv** — dependency management (`pyproject.toml` + `uv.lock`)

## Architecture

```
HTTP → router.py → service.py → models.py → SQLite / PostgreSQL
                 ↘ BackgroundTasks → classifier (CLASSIFIER_URL, optional)
```

- **`router.py`** — FastAPI router on `/notes`; wires up BackgroundTasks after POST
- **`service.py`** — business logic; raises `HTTPException` on 404/conflict
- **`models.py`** — `Note` + `NoteTag` ORM entities; `tags` exposed as a list property
- **`schemas.py`** — Pydantic `NoteRequest`, `TagsRequest`, `NoteResponse`
- **`database.py`** — engine + session factory; `DATABASE_URL` env var

## Running it

```bash
uv sync                                          # install deps
uvicorn notes_api.main:app --port 8081           # start the server
```

The API comes up at `http://localhost:8081`. Data persists to `notes.db` in the
working directory. Set `DATABASE_URL` for PostgreSQL:

```bash
DATABASE_URL=postgresql://user:pass@localhost/notesdb \
  uvicorn notes_api.main:app --port 8081
```

Set `CLASSIFIER_URL` to enable automatic tag enrichment after note creation:

```bash
CLASSIFIER_URL=http://localhost:8000 \
  uvicorn notes_api.main:app --port 8081
```

If `CLASSIFIER_URL` is unset (the default), classification is skipped — note
creation still works normally.

## API

| Method | Path               | Body           | Status | Notes                                            |
|--------|--------------------|----------------|--------|--------------------------------------------------|
| GET    | `/notes`           | —              | 200    | List notes; optional `?q=` text, `?tag=`, and `?published_after=`/`?published_before=` (ISO date) filters |
| GET    | `/notes/{id}`      | —              | 200    | 404 if not found                                 |
| POST   | `/notes`           | `NoteRequest`  | 201    | 400/422 if title/content blank or invalid        |
| PUT    | `/notes/{id}`      | `NoteRequest`  | 200    | 404 if not found                                 |
| PUT    | `/notes/{id}/tags` | `TagsRequest`  | 200    | Replace tags (idempotent writeback; `SYS-005`)   |
| DELETE | `/notes/{id}`      | —              | 204    | 404 if not found                                 |

`NoteRequest`: `{ "title": "...", "content": "...", "tags": ["..."], "published_at": "2014-03-15" }`
— `tags` and `published_at` are optional. `published_at` is the article's own
publication date (ISO 8601), distinct from the server-controlled `created_at`
(when the note was saved); it's what makes the date-range filters meaningful.
The server controls `id`, `created_at`, `updated_at`, and `enrichment_status`.

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

Tests run fully offline — no `CLASSIFIER_URL` or `DATABASE_URL` needed.
