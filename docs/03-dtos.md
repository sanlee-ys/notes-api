# DTOs

**DTO = Data Transfer Object.** It's a class whose only job is to carry data
across a boundary. In this project that boundary is HTTP: a DTO defines the exact
shape of what a client can **send in** and what they **get back**.

We have two:

- `dto/NoteRequest.java` — what a client may send (create/update input).
- `dto/NoteResponse.java` — what the API sends back.

Both are Java **records** (more on that below).

## The obvious question: why not just use the `Note` entity?

We already have a `Note` class. Why not accept and return that directly and skip
two extra files? Three reasons, and you actually hit the first one live while
building this:

### 1. Security — clients shouldn't set server-controlled fields

The `Note` entity has `id`, `createdAt`, and `updatedAt`. Those are owned by the
database and Hibernate. If the controller accepted a raw `Note`, a client could
POST:

```json
{"id": 999, "createdAt": "1999-01-01T00:00:00Z", "title": "x", "content": "y"}
```

...and try to overwrite fields they have no business setting. (This class of bug
has a name: *mass assignment* / *over-posting*.)

`NoteRequest` simply **has no `id` or timestamp fields**, so there is nothing for
a malicious or careless client to set. We tested exactly this: sending an `id` of
999 was silently ignored and the server assigned the real id. The DTO is the wall.

### 2. Decoupling — the API shape and the DB shape can change independently

Today `NoteResponse` looks a lot like `Note`. But the moment you want to rename a
database column without breaking clients, or hide an internal field, or add a
computed field that isn't stored — you need them to be separate. The DTO is your
**public contract**; the entity is your **storage detail**. Welding them together
means every database change risks breaking your API.

### 3. Validation lives naturally on the input DTO

`NoteRequest` carries the rules for "what is a valid create request":

```java
public record NoteRequest(
    @NotBlank @Size(max = 255)   String title,
    @NotBlank @Size(max = 10_000) String content
) {}
```

When the controller marks it `@Valid`, those annotations run before your code
does. A blank title never reaches the service. (If you know Pydantic, this is the
same feeling: the type *is* the validation.)

## Records — the modern-Java part

`NoteRequest` and `NoteResponse` are declared with `record`, not `class`. A record
is a compact, **immutable** data carrier. This one line:

```java
public record NoteResponse(Long id, String title, String content,
                           Instant createdAt, Instant updatedAt) {}
```

...auto-generates the constructor, accessor methods (`id()`, `title()`, …),
`equals`, `hashCode`, and `toString`. The fields can't be changed after
construction.

The closest Python analogy is a frozen dataclass:

```python
@dataclass(frozen=True)
class NoteResponse:
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
```

Records arrived in Java 16 (2021), so if your Java memories predate that, they're
genuinely new — and they're perfect for DTOs.

## The mapping between DTO and entity

Something has to convert between the two. We keep that in one place:

- **Entity → response:** `NoteResponse.from(note)` — a static factory on the
  record that reads the entity's getters and builds the DTO.
- **Request → entity (create/update):** the controller does
  `new Note(request.title(), request.content())`.

For a small project, hand-written mapping like this is the clearest — you can see
exactly what crosses the boundary. (Larger projects sometimes use a library like
MapStruct to generate it, but that's magic you don't need yet.)

## Rule of thumb

> Entities are for talking to the database. DTOs are for talking to the outside
> world. Don't let one masquerade as the other.
