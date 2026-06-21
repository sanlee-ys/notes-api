# Search & queries

`GET /notes` now takes two optional query params:

- `?q=` — case-insensitive text to find in the title **or** content
- `?tag=` — a tag the note must have

They combine (AND), and with neither present you get every note. This note is
about *how* that search is implemented, and the two ways Spring Data lets you
write queries.

## Two ways to ask the database a question

In Spring Data, custom queries come in two flavors:

1. **Derived queries** — you encode the query in the *method name* and Spring
   generates it. e.g. `findByTitleContainingIgnoreCase(String title)` becomes
   "WHERE LOWER(title) LIKE LOWER('%...%')". Zero query code; great for simple
   one-field lookups.

2. **`@Query`** — you write the query yourself. Needed when the logic is too
   complex for a method name.

Our search has **optional, combinable filters**, which a single method name
can't express cleanly, so we used `@Query`. (You can see a derived-query example
in this note's [last section](#the-derived-query-alternative).)

## The query, line by line

From `repository/NoteRepository.java`:

```java
@Query("""
    SELECT DISTINCT n FROM Note n LEFT JOIN n.tags t
    WHERE (:q IS NULL
           OR LOWER(n.title) LIKE LOWER(CONCAT('%', :q, '%'))
           OR LOWER(n.content) LIKE LOWER(CONCAT('%', :q, '%')))
      AND (:tag IS NULL OR LOWER(t) = LOWER(:tag))
    """)
List<Note> search(@Param("q") String q, @Param("tag") String tag);
```

**It's JPQL, not SQL.** JPQL (Jakarta Persistence Query Language) queries your
*entities and fields* — `Note`, `n.title` — not database tables and columns.
Hibernate translates it to the right SQL for whatever database is underneath, so
the same query works on H2 today and PostgreSQL later. (`n` is just an alias for
a `Note`, like a loop variable.)

Piece by piece:

- **`SELECT DISTINCT n`** — return whole `Note` entities; `DISTINCT` removes
  duplicates (see the join below).
- **`LEFT JOIN n.tags t`** — walk into each note's `tags` collection, aliasing
  each tag as `t`. `LEFT` keeps notes that have *no* tags. A note with 3 tags
  produces 3 rows here — which is exactly why we need `DISTINCT`.
- **`:q IS NULL OR ...`** — the **optional-filter pattern**. If the caller passes
  `q = null`, the `:q IS NULL` half is true and the text condition is skipped
  entirely. If `q` has a value, we match it against title or content.
- **`LOWER(...) LIKE LOWER(CONCAT('%', :q, '%'))`** — case-insensitive "contains".
  `CONCAT('%', :q, '%')` wraps the term in SQL wildcards; lowercasing both sides
  makes `MILK` match `milk`.
- **`:tag IS NULL OR LOWER(t) = LOWER(:tag)`** — same optional pattern for the
  tag, matched case-insensitively against the joined tag values.

The payoff: **one query covers all four cases** — no filter, text only, tag only,
or both — instead of four separate methods or hand-built query strings.

If you've used SQLAlchemy, the spirit is the same as conditionally chaining
`.filter(...)` clauses, just expressed declaratively with null-guards instead of
`if q is not None:` branches.

### Aside: text blocks

The `""" ... """` is a **text block** (Java 15+), for multi-line strings without
`\n` and `+` clutter. If your last Java memories are from before then, this is one
of the nicer quality-of-life additions.

## Wiring it through the layers

The query is the hard part; the rest is plumbing:

- **Controller** (`NoteController.getAll`) declares the params optional:
  ```java
  public List<NoteResponse> getAll(
          @RequestParam(required = false) String q,
          @RequestParam(required = false) String tag) { ... }
  ```
  `@RequestParam` binds `?q=...&tag=...` from the URL. `required = false` means
  the endpoint still works with no params at all.

- **Service** (`NoteService.search`) normalizes blank input to `null`, so `?q=`
  (empty) is treated the same as omitting it — and `null` is what the query's
  `IS NULL` guard expects.

- **Repository** runs the query.

Same top-to-bottom flow as every other endpoint (see
[architecture](01-architecture.md)) — only the data-access method is new.

## The derived-query alternative

If we only needed plain text search (no optional combining), we wouldn't write
JPQL at all — a method name would do:

```java
List<Note> findByTitleContainingIgnoreCaseOrContentContainingIgnoreCase(
        String title, String content);
```

Spring reads that name and generates the query. It's perfect for simple cases.
We reached for `@Query` specifically because **optional, combinable filters**
outgrow what a method name can say — the standard signal to switch from derived
queries to an explicit one.
