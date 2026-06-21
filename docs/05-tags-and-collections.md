# Tags & JPA collections

This note covers how a note carries **tags**, and the JPA feature that makes it
work: `@ElementCollection`. It's also a small lesson in *choosing the simplest
model that fits*.

## The decision: two ways to model tags

There were two reasonable designs:

- **A — tags as a collection of strings** (what we built). Each note owns a list
  of plain strings.
- **B — a `Tag` entity with a many-to-many relationship.** Tags become shared,
  first-class rows in their own table.

We chose **A** because it teaches one new JPA concept cleanly and is genuinely
enough for "labels on a note." We'll graduate to **B** later as its own lesson —
same "feel the simple version, then meet the problem the richer version solves"
approach we used for [DTOs](03-dtos.md). The trade-off is spelled out at the
[bottom of this note](#when-to-upgrade-to-a-tag-entity).

## `@ElementCollection`: a collection of basic values

A normal column holds one value. But "a set of tags" is many values. JPA can't
cram a list into a single column, so `@ElementCollection` tells it to store the
values in a **separate table**, linked back to the owning note. From
`model/Note.java`:

```java
@ElementCollection(fetch = FetchType.EAGER)
@CollectionTable(name = "note_tags", joinColumns = @JoinColumn(name = "note_id"))
@Column(name = "tag", length = 50)
private Set<String> tags = new LinkedHashSet<>();
```

Decoded annotation by annotation:

| Annotation | Meaning |
|------------|---------|
| `@ElementCollection` | "This collection of basic values lives in its own table." |
| `@CollectionTable(name = "note_tags", ...)` | The side table's name. |
| `@JoinColumn(name = "note_id")` | The column linking each tag row back to its note. |
| `@Column(name = "tag", length = 50)` | The column holding the tag string itself. |
| `fetch = FetchType.EAGER` | Load the tags whenever you load the note (see below). |

The resulting table is just:

```
note_tags
┌─────────┬──────────────┐
│ note_id │ tag          │
├─────────┼──────────────┤
│   1     │ spring       │
│   1     │ java         │
│   1     │ spring-data  │
└─────────┴──────────────┘
```

One row per (note, tag) pair. No `Tag` entity, no join table — the strings just
live here.

### EAGER vs LAZY

`EAGER` means the tags load in the same query as the note. The alternative,
`LAZY`, would defer loading until you actually call `getTags()`. We chose EAGER
because we serialize notes to JSON *after* the database transaction ends, and a
lazy collection accessed after the transaction closes throws. For a small app
with a handful of tags, EAGER is the simple, safe choice. (At larger scale, eager
collections can cause performance surprises — a topic for another day.)

## Why a `Set`, and the ordering gotcha

`tags` is a `Set<String>`, not a `List<String>`. A set can't contain the same
element twice, so a note can't end up with `java` listed twice — the dedupe is
free.

**But:** a `Set` is, by definition, unordered. We initialize the field with a
`LinkedHashSet` (which *does* remember insertion order), yet once Hibernate loads
a note from the database it swaps in its own set implementation, and the stored
order is **not** the order you inserted. You can see this in the demo: inserting
`java, spring, java, "", spring-data` came back as `spring, java, spring-data`.

If you need tags to keep a stable, meaningful order, the fix is a
`List<String>` plus an `@OrderColumn` (which adds an index column to the side
table). For labels, order doesn't matter, so an unordered `Set` is the right call.

> Lesson: choosing `Set` vs `List` is a real modeling decision — `Set` = "unique,
> unordered," `List` = "ordered, duplicates allowed."

## Cleaning the input

Clients send messy tags. We normalize them in the controller before they ever
reach the entity (`NoteController.cleanTags`):

```java
return raw.stream()
        .filter(tag -> tag != null)
        .map(String::trim)
        .filter(tag -> !tag.isEmpty())
        .collect(Collectors.toCollection(LinkedHashSet::new));
```

This is a **stream pipeline** — Java's equivalent of chaining
filter/map operations (think a list comprehension with steps). It drops nulls,
trims whitespace, drops anything now empty, and collects into a set (which
removes exact duplicates). Case is left as the client sent it; lowercasing would
be a separate decision (it makes `Java` and `java` the same tag, which you may or
may not want).

We keep this at the controller boundary because it's about *cleaning untrusted
input*, which is a web-layer concern — the same place the DTOs live.

## Validating a collection

`dto/NoteRequest.java` shows two different validation targets on one field:

```java
@Size(max = 20, message = "a note can have at most 20 tags")
Set<@Size(max = 50, message = "each tag must be at most 50 characters") String> tags
```

- The `@Size` on the **field** limits the *number* of tags (≤ 20).
- The `@Size` on the **type argument** (inside the `<>`) limits the *length of
  each tag* (≤ 50 chars). This is a "container element constraint."

When a single tag is too long, the error comes back keyed as `tags[]` — Spring's
way of saying "an element of the tags collection failed." Tags are optional: omit
the field entirely and the request is still valid.

## When to upgrade to a `Tag` entity

`@ElementCollection` is the right tool when tags are *owned by* one note and have
no independent existence. You should reach for a separate `Tag` entity +
`@ManyToMany` when you need tags to be **shared, first-class things**, e.g.:

- list every tag in the system, with how many notes use each;
- rename a tag once and have it change everywhere;
- attach metadata to a tag (color, description);
- guarantee there's exactly one canonical `java` row.

With `@ElementCollection`, the string `java` is duplicated across every note's
rows — there's no single "java" to point at. That's the limitation that a `Tag`
entity removes, and it'll make a good future note.
