# Kafka: partitions & brokers

We just made `notes-api` publish its first Kafka message and watched it land in
kafka-ui. Two words showed up on that screen — **broker** and **partition** — and
they're the two ideas that make Kafka *Kafka*. Here's what they mean, in plain
language, tied to the picture we actually saw.

If you've used Kafka from Python before (`confluent_kafka` / `kafka-python`), none of
the *concepts* here are new — only the Java/Spring wrapping is. That's the whole point
of this exercise.

## The one analogy: a grocery store

Picture a **grocery store** with **checkout lanes**.

| Kafka | Grocery store |
|---|---|
| **Broker** | the store building (one server) |
| **Topic** | a category of orders, e.g. `smoke-test` |
| **Partition** | one checkout lane |
| **Offset** | your position in that lane's line: 0, 1, 2… |
| **Key** | the rule for *which lane* you're sent to |

Everything below is just one cell of this table.

## Broker = one Kafka server

A **broker** is a single Kafka server — one process on one machine — that receives
messages, stores them on disk in order, and hands them out to whoever asks. It's the
store building.

Your local setup has **one broker** (the `notes-kafka` container). When the app
connected with `bootstrap-servers=localhost:9092`, it was pointing at that one store.
In Python this was your `bootstrap.servers` — exact same idea.

A real deployment runs **several brokers** = several stores sharing the work (a
*cluster*), for two reasons:
- **Scale** — more stores handle more shoppers.
- **Safety** — each lane's orders are *copied* to another store (**replication**), so
  if one store burns down, nothing is lost. (With one broker there's no backup — fine
  for local dev, never for production.)

## Topic & partition = lanes within the store

A **topic** is a named stream of messages — `smoke-test` is ours. But a topic isn't
one big line; it's split into **partitions**, and the partition is the real unit of
storage: an **append-only log**. New messages go on the **end**, and they're never
reordered.

That's a checkout lane: people join the back, get served in arrival order, and you
can't shuffle the line.

**Why split a topic into lanes at all?** Parallelism. One lane only moves so fast; ten
lanes serve ten shoppers at once — and ten different consumers can each read one lane
in parallel. Partitions are *how Kafka scales*.

Our `smoke-test` topic has exactly **one** partition (partition `0`) — which is why
both messages showed up on partition 0 in kafka-ui.

## Offset = position in the lane

Each message in a partition gets an **offset** — its slot number, counting from 0. You
saw this directly: the first message was **offset 0**, the second **offset 1**.

Offsets are how a consumer remembers its place ("I've read up to 5; give me 6 next").
The log keeps messages by position — it doesn't delete them when read — so several
consumers can read the same lane independently, each tracking its own offset. That
durable, replayable log is Kafka's superpower over a plain queue.

## Key = which lane you're sent to

When you send a message you can attach a **key**. Kafka hashes the key to choose a
partition, with one guarantee: **the same key always goes to the same partition.**

You named your message's key `note-1`. With a single partition that's cosmetic — but
it's rehearsing the real design. When `notes-api` publishes real `NoteCreated` events,
the **key will be the note's id**. So every event about note #42 lands in the same
lane, in order — even while events for *different* notes spread across lanes for
throughput. Per-key order, global parallelism. That's the trick.

No key? Kafka spreads messages across lanes round-robin — fast, but with no ordering
guarantee between them.

## What we saw, in one picture

```
topic: smoke-test   (on broker "notes-kafka", localhost:9092)
└── partition 0  ← the only lane
      offset 0:  key=smoke-key  "hello from notes-api @ ..."
      offset 1:  key=note-1     "notes-api speaks Kafka ..."
```

One store, one lane, two shoppers in order. Add lanes and the **key** starts deciding
who goes where; add stores and you get **scale** and **backups**. Everything else in
Kafka is built on top of these two ideas.

## Where this lives in the code

- Producer: `src/main/java/com/notes/api/smoke/SmokeKafkaProducer.java` (throwaway — it
  gets replaced by real `NoteCreated` events).
- Broker address + serializers: `src/main/resources/application.properties`.
- The broker itself: the `local/docker-compose.yml` stack.
