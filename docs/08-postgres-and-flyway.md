# PostgreSQL & Flyway

Until now the app used **H2**, an in-memory database that's reset every time the
app stops. Great for tests and quick runs, useless for anything real. This note
covers moving to **PostgreSQL** for actual durable storage, managing the schema
with **Flyway**, and the three real-world snags we hit doing it (each is a keeper).

The headline change: with Postgres, a note you create **survives an app restart**.
We proved it — created a note, fully stopped the app, queried Postgres directly to
see the row on disk, restarted, and read it back.

## Two profiles: H2 by default, Postgres on demand

We did **not** rip out H2. Instead we used **Spring profiles** so each database is
used where it's best:

- **Default** (`application.properties`) → H2. Zero setup, so tests and a quick
  `mvnw spring-boot:run` just work. Flyway is turned **off** here.
- **`postgres`** (`application-postgres.properties`) → PostgreSQL + Flyway.

A profile is just a named bundle of config. `application-postgres.properties` is
loaded *on top of* the defaults only when the `postgres` profile is active.
Activate it with an env var or a flag:

```bash
# env var
SPRING_PROFILES_ACTIVE=postgres ./mvnw spring-boot:run
# or a flag
./mvnw spring-boot:run -Dspring-boot.run.profiles=postgres
```

Keeping the **tests on H2** means they stay fast and need no running database —
while the app can talk to real Postgres when you ask it to. (The trade-off of that
choice bites us in snag #3 below.)

## External configuration & secrets

The Postgres profile points at the database and externalizes the password:

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/notesdb
spring.datasource.username=postgres
spring.datasource.password=${POSTGRES_PASSWORD:postgres}
```

`${POSTGRES_PASSWORD:postgres}` means "use the `POSTGRES_PASSWORD` environment
variable, or fall back to `postgres` for local dev." **Real secrets never get
committed** — they come from the environment in production. The committed fallback
is only good enough for a throwaway local database. (A further real-world step:
give the app its own limited-privilege database user instead of the `postgres`
superuser.)

The `org.postgresql:postgresql` JDBC driver (runtime scope) is what lets Java
speak Postgres's wire protocol — the equivalent of `psycopg2` in Python.

## Flyway: versioned schema migrations

With H2 we let Hibernate auto-create tables from the entities. That's convenient
but unsafe for a real database: you get no history, no review, no control over
exactly what DDL runs. **Flyway** fixes that — your schema is a series of numbered
SQL scripts, applied in order, each exactly once.

Our one migration, `src/main/resources/db/migration/V1__create_notes_and_tags.sql`,
creates the `notes` and `note_tags` tables. The naming matters:

```
V1__create_notes_and_tags.sql
│ │  └ description (underscores → spaces)
│ └ double underscore separator
└ version number
```

On startup Flyway:
1. creates a `flyway_schema_history` table if absent,
2. finds migrations newer than what's recorded,
3. runs them and records each.

Run it twice and the second start does nothing — v1 is already applied. The next
schema change goes in a **new** `V2__...sql`; you never edit an applied migration.

### Hibernate's role: `validate`

In the Postgres profile:

```properties
spring.jpa.hibernate.ddl-auto=validate
```

Hibernate no longer creates or changes anything — Flyway owns the schema. Hibernate
only **validates** that the entities line up with the tables Flyway built. If your
`Note` entity and your migration drift apart, the app refuses to start. That's a
feature: it catches mismatches at boot instead of at 2 a.m. in production.

## Three snags we hit (the real lessons)

### Snag 1 — Flyway didn't run at all

First Postgres boot: Flyway never executed, no tables, app failed validation.
Cause: in **Spring Boot 4**, `flyway-core` gives you the *library* but not Boot's
*auto-configuration*. The fix was to depend on **`spring-boot-starter-flyway`**,
which pulls both. This is the same modularization theme as the
[starters](04-pom-and-maven.md) and the [test slices](07-testing.md): in Boot 4,
auto-configuration lives in per-feature modules, and a raw library jar doesn't
include it.

### Snag 2 — timestamps had to match (they did)

`validate` is strict about column types. Our migration uses
`TIMESTAMP(6) WITH TIME ZONE` for `created_at`/`updated_at`, which is what
Hibernate maps `java.time.Instant` to on Postgres — so validation passed. Had they
not matched, the app would have failed at startup with a clear "wrong column type"
message. (That's `validate` doing its job.)

### Snag 3 — "works on H2, breaks on Postgres"

The biggest lesson. The search query that passed all our H2 tests blew up on
Postgres:

```
ERROR: function lower(bytea) does not exist
```

When `q`/`tag` are `null`, the query bound an **untyped null**. H2 didn't care;
Postgres, asked to compute `LOWER(<untyped null>)`, guessed the type was `bytea`
and there's no `lower(bytea)`. The fix was to give the parameter an explicit type:

```sql
LOWER(CAST(:tag AS String))   -- not LOWER(:tag)
```

Why it matters: **our tests are green on H2, but H2 is not Postgres.** Subtle
dialect differences (null typing, functions, casing) only show up against the real
engine. In a serious project you'd run at least some tests against Postgres too
(e.g. with Testcontainers) precisely to catch this class of bug before production.

## Inspecting the database

Postgres ships with `psql`. With the app *not* running, you can still see the data:

```bash
psql -U postgres -d notesdb -c "SELECT id, title FROM notes;"
psql -U postgres -d notesdb -c "SELECT * FROM note_tags;"
psql -U postgres -d notesdb -c "SELECT * FROM flyway_schema_history;"
```

That independence — the data existing whether or not your app is up — is the whole
point of a real database.
