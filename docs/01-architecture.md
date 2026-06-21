# Why it's structured this way

This project has more files than the work strictly requires. A single class could
read the request, run the logic, and hit the database. So why split it into a
controller, a service, a repository, an entity, and some DTOs?

Short answer: **each layer has exactly one job, and depends only on the layer
below it.** That makes each piece easy to understand, test, and change in
isolation. This is the standard layered design behind almost every Spring backend,
so learning it here transfers everywhere.

## The layers

| Layer | File | One-sentence job |
|-------|------|------------------|
| Controller | `controller/NoteController.java` | Translate HTTP ↔ Java method calls. |
| DTOs | `dto/NoteRequest.java`, `dto/NoteResponse.java` | Define the shape of data crossing the HTTP boundary. |
| Service | `service/NoteService.java` | Hold the business rules. |
| Repository | `repository/NoteRepository.java` | Read/write the database. |
| Entity | `model/Note.java` | Map a Java object to a database row. |
| Error handling | `exception/` | Turn exceptions into clean HTTP responses. |

## Follow one request all the way down

Take `POST /notes` with body `{"title":"Buy milk","content":"2% and oat"}`:

1. **Controller** (`NoteController.create`) receives the HTTP request. Spring has
   already parsed the JSON body into a `NoteRequest` object and run validation on
   it. The controller's job is done in two lines: build a `Note` from the request,
   hand it to the service, and wrap the result in a `NoteResponse`.

2. **Service** (`NoteService.create`) applies the rules. For create that's simple
   ("just save it"), but for `update` it's a read-modify-write inside a
   transaction, and for `findById` it's "throw a 404 exception if missing." This
   is where logic lives so it isn't duplicated across controllers.

3. **Repository** (`NoteRepository.save`) does the actual database write. We never
   wrote this method — Spring Data generated it (see [DTOs note](03-dtos.md) and
   the repository file's comments).

4. **Entity** (`Note`) is what gets stored. Hibernate turns the object into an
   `INSERT` into the `notes` table and fills in the generated `id` and the
   `createdAt`/`updatedAt` timestamps.

Then the result travels back up: entity → `NoteResponse` DTO → JSON → HTTP 201.

## Why the dependencies point one direction

Notice the arrows only go **downward**: the controller knows about the service,
the service knows about the repository, the repository knows about the entity.
Nothing points back up. The database layer has no idea the web exists.

That one-way dependency is what lets you:

- **Test a layer alone.** You can unit-test `NoteService` by handing it a fake
  repository — no web server, no database. (`new NoteService(mockRepo)`.)
- **Swap a layer.** Move from H2 to PostgreSQL and only the repository/config
  layer cares. Add a GraphQL API and only the web layer changes.
- **Reason locally.** A bug in HTTP status codes is in the controller. A bug in
  "what counts as a valid update" is in the service. You know where to look.

## Who wires it all together?

You never write `new NoteController(new NoteService(new NoteRepository(...)))`.
Spring does. At startup it sees `@RestController`, `@Service`, and the repository
interface, creates one instance ("bean") of each, and passes them into each
other's constructors — that's **dependency injection**. Your classes just declare
what they need in their constructor and trust Spring to provide it.

Python analogy: imagine a framework that scans your project, notices your
`NoteService` constructor wants a `NoteRepository`, and automatically constructs
and injects one — instead of you wiring objects together in `main()`.

## Where to go next

- [Controllers](02-controllers.md) — zoom into the top layer.
- [DTOs](03-dtos.md) — why `NoteRequest`/`NoteResponse` exist separately from `Note`.
