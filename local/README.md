# notes-api — local dev stack

Single-node **Kafka** (KRaft mode, no ZooKeeper) + **kafka-ui**, for the Phase 0 event-driven
work. Spin this up before running the app's Kafka code.

## Prerequisites

| Need | Why / how |
|------|-----------|
| **Docker Desktop running** | Container engine + Compose. Install ≠ running — launch it and wait for "Engine running". |
| **WSL2** | Docker Desktop's backend on Windows: `wsl --install`, then reboot. |
| **JAVA_HOME** (for the app) | `C:\Program Files\Java\jdk-26.0.1`. Not set system-wide yet (risk R7); the Maven build needs it. |

> `docker` is on PATH in a normal terminal once Docker Desktop is installed. If a script can't
> find it, prepend `C:\Program Files\Docker\Docker\resources\bin`.

## Bring it up

```powershell
docker compose -f local/docker-compose.yml up -d
```

Then:
- **kafka-ui → http://localhost:8080** (cluster "local") to watch topics and messages. It's
  Spring-based, so give it ~10–15s to boot.
- The Spring app connects to the broker at **localhost:9092**.

Verify the broker is healthy:
```powershell
docker compose -f local/docker-compose.yml ps          # kafka should read "Up (healthy)"
docker exec notes-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

## Tear down

```powershell
docker compose -f local/docker-compose.yml down         # stop + remove containers and the network
```

## Why confluent and not apache/kafka

This compose uses `confluentinc/cp-kafka`, not the official `apache/kafka`. The apache image's
KRaft **auto-format step** (`StorageTool`) rejects this stack's custom dual advertised listeners
with `advertised.listeners cannot use the nonroutable meta-address 0.0.0.0` — *even though*
`advertised.listeners` is set correctly to routable addresses (confirmed in the generated
`server.properties`). It's the image's bootstrap, not the config. Confluent's image formats
cleanly with the identical listener setup. Diagnosis steps are under Troubleshooting → #3.

## Troubleshooting

Real issues hit standing this up, with the fix:

**1. `java: command not found` / the app won't build**
`JAVA_HOME` isn't set. Point it at the JDK for the session:
```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-26.0.1'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
```
A permanent `setx JAVA_HOME "C:\Program Files\Java\jdk-26.0.1"` removes the papercut (risk R7).

**2. `Cannot connect to the Docker daemon` / "daemon not responding"**
Docker Desktop is installed but the **engine isn't started**. Launch Docker Desktop, accept the
first-run terms, and wait for the whale icon to read "Engine running".

**3. Kafka container exits (1) on start; log shows `advertised.listeners cannot use 0.0.0.0`**
You're on the `apache/kafka` image — its KRaft auto-format step doesn't honor the advertised
listeners during `kafka-storage format`. Fix: use `confluentinc/cp-kafka` (this compose already
does). How it was isolated — useful for any "container won't start" case:
```powershell
docker logs notes-kafka                                              # the exception + which step failed (StorageTool = format)
docker inspect notes-kafka --format '{{range .Config.Env}}{{println .}}{{end}}'   # confirm the env vars are right
docker cp notes-kafka:/opt/kafka/config/server.properties .          # confirm the generated config is right
```
Env and generated config were both correct → the problem was the image, not our config. Swapping
the image (one line) fixed it.

**4. kafka-ui shows no cluster / blank page**
It's Spring-based and slow to boot — wait ~10–15s and refresh. If it still can't see the broker,
confirm it points at the **internal** listener (`kafka:29092` over the docker network), not
`localhost:9092` (that's the host listener, only reachable from Windows).
