# notes-api

A small, well-commented **Notes REST API** built with **Spring Boot 4** — a learning
project for getting back into Java by building something real rather than toy snippets.
It demonstrates the classic layered architecture (controller → service → repository →
entity), DTO-based request/response contracts, bean validation, and centralized error
handling.

## Tech stack

- **Java 21** (bytecode target; builds fine on newer JDKs)
- **Spring Boot 4.1** — Web MVC, Data JPA, Validation
- **Hibernate** ORM with an **H2** in-memory database
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

The API comes up at `http://localhost:8080`.

## API

| Method | Path          | Body            | Success | Notes                         |
|--------|---------------|-----------------|---------|-------------------------------|
| GET    | `/notes`      | —               | 200     | List all notes                |
| GET    | `/notes/{id}` | —               | 200     | 404 if not found              |
| POST   | `/notes`      | `NoteRequest`   | 201     | 400 if title/content blank    |
| PUT    | `/notes/{id}` | `NoteRequest`   | 200     | 404 if not found, 400 if invalid |
| DELETE | `/notes/{id}` | —               | 204     | 404 if not found              |

`NoteRequest` is `{ "title": "...", "content": "..." }`. The server controls `id`,
`createdAt`, and `updatedAt` — clients cannot set them.

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

## Status

Working CRUD slice with validation. Possible next steps: tags, search, automated
tests (MockMvc / `@DataJpaTest`), and swapping H2 for PostgreSQL.
