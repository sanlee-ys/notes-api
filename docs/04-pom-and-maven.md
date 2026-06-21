# pom.xml & Maven (for the 6-years-away crowd)

## What Maven even is

**Maven** is Java's build tool and dependency manager. In Python terms, it rolls
several tools you already know into one:

| Maven does… | Python equivalent |
|-------------|-------------------|
| Downloads your dependencies | `pip install` |
| Records which dependencies you need | `requirements.txt` / `pyproject.toml` |
| Caches downloaded libraries | the wheels/`site-packages` cache (here: `~/.m2/repository`) |
| Compiles + tests + packages your app | `setup.py build` / `tox` / `build` |

It's configured by one file: **`pom.xml`** ("Project Object Model"). Think of it
as `pyproject.toml`'s heavier, XML-flavored ancestor.

## The whole file, section by section

Open `pom.xml` in the project root. Here's what each part means.

### Coordinates — the project's identity

```xml
<groupId>com.notes</groupId>
<artifactId>notes-api</artifactId>
<version>0.0.1-SNAPSHOT</version>
```

Every Maven project (and every dependency) is identified by this trio:
group + artifact + version. It's how libraries are addressed in the global
repository. `-SNAPSHOT` just means "in-development, not a released version."

### Parent — where all the sane defaults come from

```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.0</version>
</parent>
```

This is the big one. By inheriting from `spring-boot-starter-parent`, our tiny
pom gets:

- **Dependency version management.** Notice the dependencies below have **no
  version numbers** — the parent already knows which versions of Spring, Hibernate,
  Jackson, etc. work together. You opt into a curated, tested set instead of
  hand-picking versions and praying they're compatible. (This is the thing pip
  doesn't really do for you.)
- **Sensible plugin configuration** for compiling, testing, and packaging.

Changing that one version number (`4.1.0`) upgrades the whole Spring Boot stack.

### Properties — project-wide settings

```xml
<properties>
    <java.version>21</java.version>
</properties>
```

Sets the Java language level the code is compiled to. We target 21 (an LTS
release) even though the JDK installed may be newer — see the main `README` /
project notes.

### Dependencies — what we pull in

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-webmvc</artifactId>
</dependency>
```

The key concept here is a **starter**. A starter isn't a single library — it's a
curated *bundle*. `spring-boot-starter-webmvc` drags in everything you need to
build a web API (the Spring web framework, an embedded Tomcat server, the Jackson
JSON library, …) as one dependency. Our starters:

- `spring-boot-starter-webmvc` — REST endpoints + embedded web server.
- `spring-boot-starter-data-jpa` — Spring Data + Hibernate (database access).
- `spring-boot-starter-validation` — the `@NotBlank`/`@Size` validation.
- `spring-boot-h2console` — the H2 database's web console.
- `h2` (scope `runtime`) — the in-memory database driver. `runtime` means it's
  needed to *run*, but your code never imports it directly.
- the `*-test` starters (scope `test`) — testing tools, only on the test classpath.

> **"Wait, isn't it `spring-boot-starter-web`?"** It used to be. Spring Boot 4
> split the old mega-starters into smaller modular ones, so `-web` became
> `-webmvc`, and the single `spring-boot-starter-test` became per-module test
> starters. If you're following an older tutorial, that's the main naming gotcha.

### Build plugin — how it becomes a runnable app

```xml
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
</plugin>
```

This plugin adds the `spring-boot:run` goal (start the app) and packages
everything — your code *plus all dependencies plus an embedded server* — into one
runnable "fat" JAR. That's why a Spring Boot app ships as a single
`java -jar app.jar` with nothing else to install.

## The Maven Wrapper: why there's no `mvn install` step

You may have noticed we never installed Maven. The project includes `mvnw`
(Unix) and `mvnw.cmd` (Windows) — the **Maven Wrapper**. These scripts download
the exact Maven version the project expects, on first use, into a cache. Benefits:

- Nobody has to install Maven globally.
- Everyone builds with the *same* Maven version — reproducible builds.

So you always run `./mvnw ...` (or `.\mvnw.cmd ...`), never a system `mvn`.

## Commands you'll actually use

| Command | What it does |
|---------|--------------|
| `./mvnw compile` | Compile the source. |
| `./mvnw test` | Compile + run the tests. |
| `./mvnw spring-boot:run` | Start the app (dev). |
| `./mvnw package` | Build the runnable JAR into `target/`. |
| `./mvnw clean` | Delete `target/` (build output). |

On Windows: `.\mvnw.cmd <same goals>`.

## Mental model to keep

> `pom.xml` declares **what** (coordinates, dependencies, Java version).
> The Spring Boot **parent** decides the compatible **versions**.
> **Starters** bundle related dependencies so you add one line, not ten.
> The **wrapper** (`mvnw`) makes the build reproducible without installing Maven.
