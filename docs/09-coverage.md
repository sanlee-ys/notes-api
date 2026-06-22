# Test coverage

"15 tests" (now 19) tells you nothing about *how much of the code they actually
run*. **Code coverage** measures that. We use **JaCoCo**, the standard JVM coverage
tool (the rough equivalent of `coverage.py` / `pytest-cov` in Python).

## Running it

JaCoCo is wired into the build, so a normal test run produces a report:

```bash
./mvnw test
# then open the HTML report:
target/site/jacoco/index.html
```

The `jacoco-maven-plugin` attaches a Java agent during the test run that records
which lines and branches execute, then writes the report.

## Current numbers

| Metric | Coverage |
|--------|----------|
| **Line** | **98.8%** (80/81) |
| **Branch** | **68.8%** (11/16) |

Per class, the controller, DTOs, entity, and exception handler are at 100% line
coverage; the service is at 95.7% (22/23).

## Line vs. branch — read both

- **Line coverage** = "did this line run at all." Easy to make high.
- **Branch coverage** = "did we test *both* sides of each `if`/`?:`/boolean
  condition." Stricter and more meaningful.

That's why our line number (99%) is much higher than our branch number (69%): most
lines run, but several conditional branches only get exercised one way.

The remaining branch gaps are all **defensive paths** we chose not to chase:

- `Note.setTags(null)` — nothing in the app ever passes null, so the null side of
  that guard never runs.
- `NoteController.cleanTags` — the null-element / blank-element filters only trigger
  for inputs our controller tests don't send.
- `NoteService.findAll()` — now unused (the controller switched to `search()`), so
  no test calls it.

Pushing these to 100% would mean writing tests for code paths that barely matter, or
deleting genuinely-unused code. Coverage is a **guide, not a target** — chasing
100% for its own sake produces low-value tests.

## What we excluded, and why

`NotesApiApplication` (the `main()` bootstrap) is excluded from the report:

```xml
<configuration>
  <excludes>
    <exclude>com/notes/api/NotesApiApplication.class</exclude>
  </excludes>
</configuration>
```

Its body is `SpringApplication.run(...)`, which can't meaningfully run under a unit
test. Including it just dragged the average down for no insight — excluding it keeps
the number honest. (Before excluding it, line coverage read 96.4%; the real figure
for testable code is 98.8%.)

## The big caveat: coverage ≠ correctness

High coverage means your tests *executed* the code, **not** that they *checked the
right things*. A test with no assertions can still rack up coverage. So:

- Coverage finds code that **no test touches at all** — a genuine blind spot, like
  the untested PUT/DELETE endpoints we found and fixed here.
- It does **not** tell you whether your assertions are meaningful.

Use it to find the holes, then make sure the tests filling them actually assert
something worthwhile.
