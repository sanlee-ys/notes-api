# Learning notes

Plain-language notes on *why* this project is built the way it is. Written for
someone comfortable with programming (and Python) but knocking the rust off Java
and Spring. Lots of hand-holding on purpose.

Suggested reading order:

1. **[Why it's structured this way](01-architecture.md)** — the big picture: the
   layers, and how one HTTP request travels through them.
2. **[Controllers](02-controllers.md)** — the layer that turns HTTP requests into
   Java method calls.
3. **[DTOs](03-dtos.md)** — what a DTO is and why we don't just hand the database
   entity to the outside world.
4. **[pom.xml & Maven](04-pom-and-maven.md)** — the build file, section by section,
   for anyone who hasn't touched Maven in years.

Each note points at the real files in `src/main/java/com/notes/api/` so you can
read the explanation and the code side by side.

## The 10-second mental model

```
HTTP request
   │
   ▼
NoteController   ← web layer: speaks HTTP + JSON, talks in DTOs
   │
   ▼
NoteService      ← business logic: the rules (404 on missing, etc.)
   │
   ▼
NoteRepository   ← data access: Spring Data generates the SQL
   │
   ▼
Note (entity)    ← one row in the H2 database `notes` table
```

A Python analogy for the whole thing: it's the same idea as a Flask/FastAPI
route → a service module → a SQLAlchemy model, just with the boundaries drawn
more formally and the wiring done by Spring instead of by hand.
