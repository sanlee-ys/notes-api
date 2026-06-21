# Controllers

A **controller** is the layer that deals with HTTP. It maps incoming requests —
a method (`GET`, `POST`, …) plus a URL path — to a Java method, and turns that
method's return value into an HTTP response. Nothing more.

If you've used Flask or FastAPI, a controller is the same idea as a module full
of route handlers:

```python
# FastAPI
@app.get("/notes/{id}")
def get_one(id: int):
    return service.find_by_id(id)
```

```java
// Spring — controller/NoteController.java
@GetMapping("/{id}")
public NoteResponse getOne(@PathVariable Long id) {
    return NoteResponse.from(service.findById(id));
}
```

Same shape: a path, a handler, a return value that becomes the response body.

## The annotations, decoded

Open `controller/NoteController.java` and you'll see these. Each one is an
instruction to Spring:

| Annotation | What it does | Python-ish analogy |
|------------|--------------|--------------------|
| `@RestController` | Marks the class as a web handler whose return values become the **response body** (as JSON). | A module of API routes. |
| `@RequestMapping("/notes")` | Prefixes every route in the class with `/notes`. | A router with a URL prefix. |
| `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping` | Map an HTTP verb (+ optional sub-path) to this method. | `@app.get(...)`, `@app.post(...)` |
| `@PathVariable Long id` | Bind the `{id}` in the URL to the method parameter. | FastAPI path params. |
| `@RequestBody NoteRequest request` | Parse the JSON request body into this object. | FastAPI body model. |
| `@Valid` | Run validation on the request body before the method runs. | Pydantic validation. |
| `@ResponseStatus(HttpStatus.CREATED)` | Set the success status code (201 instead of the default 200). | `return ..., 201` |

## How JSON gets in and out

You never call a JSON parser yourself. Spring uses a library called **Jackson**
under the hood:

- **In:** the request's JSON body → Jackson → a `NoteRequest` object handed to
  your method.
- **Out:** your method returns a `NoteResponse` (or a `List<NoteResponse>`) →
  Jackson → JSON written to the response.

That's why the controller can deal in plain Java objects and never touch raw
strings or `json.dumps`.

## Why the controller stays "thin"

Look at how little each method does — usually one or two lines that delegate to
`service`. That's deliberate. The controller's only responsibilities are:

1. HTTP concerns: paths, verbs, status codes, headers.
2. Translating between the wire format (DTOs/JSON) and the rest of the app.

It does **not** contain business rules. "What does updating a note mean?" and
"what happens if the id doesn't exist?" live in the [service](01-architecture.md),
not here. Keeping the controller thin means the real logic is testable without
spinning up a web server, and the same logic could be reused behind a different
entry point (a CLI, a message queue) without dragging HTTP along.

## What about errors?

The controller has no `try/catch`. When the service throws
`NoteNotFoundException`, two things can happen, both configured elsewhere:

- That exception is annotated `@ResponseStatus(NOT_FOUND)`, so Spring returns 404.
- Validation failures are caught centrally in `exception/GlobalExceptionHandler`,
  which returns a 400 with a `{field: message}` body.

So the controller describes the happy path, and error translation is handled in
one place. See [DTOs](03-dtos.md) for the validation side of that.
