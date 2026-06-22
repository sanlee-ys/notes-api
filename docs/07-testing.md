# Testing

The project has 19 tests across four classes. They're deliberately written at
three different "levels," which is worth understanding because the level dictates
the tool, the speed, and what each test can actually catch.

## The test pyramid

```
        ╱ full context ╲          1 test    ~4.2s   (slowest, most realistic)
       ╱  slice tests   ╲         11 tests  ~1–4s   (one layer + its infra)
      ╱   unit tests     ╲        7 tests   ~0.2s   (no framework, pure logic)
```

The measured run times line up with the shape: the pure-logic service tests run
in 0.23s for all seven; the full-context boot takes 4.2s for one. **The lesson:**
push as much testing as possible down to the fast unit level; use the slow,
realistic tests sparingly. (If you've done pytest, this is the same instinct as
"lots of plain unit tests, a few integration tests.")

## 1. Unit test — `service/NoteServiceTest`

Pure business-logic tests with **no Spring at all**. The whole framework is
replaced by Mockito:

```java
@ExtendWith(MockitoExtension.class)
class NoteServiceTest {
    @Mock        NoteRepository repository;   // a fake
    @InjectMocks NoteService    service;      // real service, fake injected in
```

- `@Mock` creates a stand-in repository that does nothing until told.
- `@InjectMocks` constructs a real `NoteService`, passing the mock to its
  constructor. **This only works because we used constructor injection** — the
  payoff we promised back in the service note.
- `when(repository.findById(99L)).thenReturn(Optional.empty())` scripts the fake.
- `verify(repository, never()).deleteById(99L)` asserts an interaction *didn't*
  happen.

Python analogy: `unittest.mock` — `when/thenReturn` is `Mock(return_value=...)`,
`verify` is `mock.assert_called_with(...)`.

These tests catch logic bugs ("does delete check existence first?") and run
almost instantly because nothing boots.

## 2. Repository slice — `repository/NoteRepositoryTest`

A mock can't catch a bug in the actual SQL/JPQL, so the `search` query is tested
against a **real (in-memory) database**:

```java
@DataJpaTest
class NoteRepositoryTest { ... }
```

`@DataJpaTest` boots just the JPA slice — entities, repositories, and an embedded
H2 — and nothing web-related. Each test method runs inside a transaction that is
**rolled back afterward**, so the three seeded notes in `@BeforeEach` never leak
between tests. This is the layer that actually verifies the optional-filter query
behaves (case-insensitivity, tag matching, AND-combination).

## 3. Web slice — `controller/NoteControllerTest`

Tests HTTP concerns without a real server or database:

```java
@WebMvcTest(NoteController.class)
class NoteControllerTest {
    @Autowired   MockMvc     mockMvc;   // fires fake HTTP requests
    @MockitoBean NoteService service;   // the service is mocked out
```

- `@WebMvcTest` loads only the controller, the JSON machinery, and the
  `@RestControllerAdvice` — not the service or database.
- `@MockitoBean` replaces the real service bean with a Mockito mock. (In Spring
  Boot 3.4+/4 this supersedes the old `@MockBean`.)
- `MockMvc` sends simulated requests and lets you assert on the response:
  ```java
  mockMvc.perform(post("/notes").contentType(APPLICATION_JSON).content("{...}"))
         .andExpect(status().isCreated())
         .andExpect(jsonPath("$.title").value("Buy milk"));
  ```

These tests confirm the web contract: 201 on create, 400 + a field error on a
blank title (and that the service is *not* called when validation fails), 404
when the service throws `NoteNotFoundException`, and that query params reach the
service. `MockMvc` is the rough equivalent of Flask's test client.

## AssertJ

Assertions use **AssertJ**, a fluent assertion library:

```java
assertThat(repository.search(null, "java"))
        .extracting(Note::getTitle)
        .containsExactlyInAnyOrder("Spring notes", "JPA tips");
```

It reads left to right and gives good failure messages. `extracting` pulls a
field off each element before asserting — handy for checking collections by one
property.

## A Boot 4 gotcha worth remembering

When these tests were first written, they wouldn't compile: the slice annotations
weren't where older tutorials put them. Spring Boot 4 **modularized** the test
support, so the import packages changed:

| Annotation | Spring Boot 3 package | Spring Boot 4 package |
|------------|-----------------------|-----------------------|
| `@DataJpaTest` | `...boot.test.autoconfigure.orm.jpa` | `...boot.data.jpa.test.autoconfigure` |
| `@WebMvcTest` | `...boot.test.autoconfigure.web.servlet` | `...boot.webmvc.test.autoconfigure` |

Same theme as the [pom.xml note](04-pom-and-maven.md): Boot 4 split one big
module into per-feature ones, and the package names followed. If an
auto-configuration import "doesn't exist," check whether it moved.

## Running them

```bash
./mvnw test                       # all tests
./mvnw test -Dtest=NoteServiceTest  # just one class
```

On Windows: `.\mvnw.cmd test ...`. The build fails if any test fails, which is
what makes this a safety net for every future change.
