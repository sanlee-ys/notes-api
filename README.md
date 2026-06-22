# notes-api

![CI](https://github.com/sanlee-ys/notes-api/actions/workflows/ci.yml/badge.svg)

A small, well-commented **Notes REST API** built with **Spring Boot 4** — a learning
project for getting back into Java by building something real rather than toy snippets.
It demonstrates the classic layered architecture (controller → service → repository →
entity), DTO-based request/response contracts, bean validation, and centralized error
handling.

## Tech stack

- **Java 21** (bytecode target; builds fine on newer JDKs)
- **Spring Boot 4.1** — Web MVC, Data JPA, Validation
- **Hibernate** ORM with **H2** (in-memory, default) or **PostgreSQL** (the `postgres` profile)
- **Flyway** schema migrations on the Postgres profile
- **Maven** (via the bundled Maven Wrapper — no global Maven install needed)

## Architecture

A request flows straight down the layers and back:

```
HTTP ─▶ NoteController ─▶ NoteService ─▶ NoteRepository ─▶ H2 (notes table)
         (DTOs in/out)    (business logic)  (Spring Data)
```

- **`NoteController`** — REST endpoints; speaks `NoteRequest`/`NoteResponse` DTOs only.
- **`NoteService`** — business rules (404 on missing, transactional read-modify-write).
- **`NoteRepository`** — an empty interface; Spring Data generates the implementation.
- **`Note`** — the JPA entity mapped to the `notes` table.
- **`GlobalExceptionHandler`** — turns validation failures into clean `400` field-error maps.

## Running it

You need a JDK 17+ on `JAVA_HOME`. Then, from the project root:

```bash
./mvnw spring-boot:run          # macOS/Linux
.\mvnw.cmd spring-boot:run      # Windows PowerShell
```

The API comes up at `http://localhost:8080`. This default uses an in-memory H2
database, so data resets on each restart.

### Running against PostgreSQL

With a Postgres reachable at `localhost:5432` and a `notesdb` database, activate
the `postgres` profile — Flyway creates the schema and data persists across restarts:

```bash
SPRING_PROFILES_ACTIVE=postgres ./mvnw spring-boot:run        # macOS/Linux
$env:SPRING_PROFILES_ACTIVE='postgres'; .\mvnw.cmd spring-boot:run   # Windows PowerShell
```

Set `POSTGRES_PASSWORD` for the DB password (defaults to `postgres` for local dev).
See [docs/08](docs/08-postgres-and-flyway.md) for the full walkthrough.

## API

| Method | Path          | Body            | Success | Notes                         |
|--------|---------------|-----------------|---------|-------------------------------|
| GET    | `/notes`      | —               | 200     | List notes; optional `?q=` text & `?tag=` filters |
| GET    | `/notes/{id}` | —               | 200     | 404 if not found              |
| POST   | `/notes`      | `NoteRequest`   | 201     | 400 if title/content blank    |
| PUT    | `/notes/{id}` | `NoteRequest`   | 200     | 404 if not found, 400 if invalid |
| DELETE | `/notes/{id}` | —               | 204     | 404 if not found              |

`NoteRequest` is `{ "title": "...", "content": "...", "tags": ["..."] }` (tags
optional). The server controls `id`, `createdAt`, and `updatedAt` — clients
cannot set them.

### Example

```bash
curl -s -X POST http://localhost:8080/notes \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy milk","content":"2% and oat"}'
# -> 201 {"id":1,"title":"Buy milk","content":"2% and oat","createdAt":"...","updatedAt":"..."}
```

A bad request returns the offending fields:

```bash
curl -s -X POST http://localhost:8080/notes \
  -H "Content-Type: application/json" -d '{"title":"","content":""}'
# -> 400 {"title":"title must not be blank","content":"content must not be blank"}
```

## Learning notes

This repo is a learning project, so it ships with plain-language concept notes in
[`docs/`](docs/README.md):

- [Why it's structured this way](docs/01-architecture.md) — the layers and a request's journey
- [Controllers](docs/02-controllers.md) — the HTTP layer and its annotations
- [DTOs](docs/03-dtos.md) — what a DTO is and why it's separate from the entity
- [pom.xml & Maven](docs/04-pom-and-maven.md) — the build file, section by section
- [Tags & JPA collections](docs/05-tags-and-collections.md) — `@ElementCollection`, `Set` vs `List`, collection validation
- [Search & queries](docs/06-search-and-queries.md) — derived queries vs `@Query`, JPQL, optional filters
- [Testing](docs/07-testing.md) — the test pyramid: Mockito, `@DataJpaTest`, `@WebMvcTest` + `MockMvc`
- [PostgreSQL & Flyway](docs/08-postgres-and-flyway.md) — profiles, external config, schema migrations
- [Test coverage](docs/09-coverage.md) — JaCoCo, line vs. branch, coverage as a guide

## Status

Working CRUD with validation, tags, and search; a 19-test suite (`./mvnw test`)
at 98.8% line / 68.8% branch coverage (JaCoCo); and an optional PostgreSQL profile
with Flyway migrations for durable storage.
