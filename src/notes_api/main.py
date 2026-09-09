"""FastAPI application entry point: app construction, lifespan, and liveness.

Wires the notes router into the app and creates database tables at startup
via the lifespan hook — sufficient for a single-process app; a migration tool
(e.g. Alembic) would take over table management if the schema ever needs
versioned changes.

The lifespan also recovers stale outbox jobs and starts a small asyncio loop
that drains due enrichment work. The loop is cancelled on shutdown.

Run locally:
    uvicorn notes_api.main:app --host 127.0.0.1 --port 8081
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator

from fastapi import FastAPI

from .database import Base, engine
from .router import router
from .tasks import process_due_jobs, recover_stale_jobs
from .telemetry import setup_tracing

logger = logging.getLogger(__name__)

# Poll interval for the outbox drain loop. The POST /notes path also kicks
# process_due_jobs via BackgroundTasks, so this is the crash-recovery cadence
# and the path that drains jobs queued while CLASSIFIER_URL was unset.
OUTBOX_POLL_SECONDS = 5.0


async def _run_outbox_loop(stop: asyncio.Event) -> None:
    """Drain due enrichment jobs until ``stop`` is set."""
    while not stop.is_set():
        try:
            await asyncio.to_thread(process_due_jobs)
        except Exception:
            logger.exception("enrichment outbox poll failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=OUTBOX_POLL_SECONDS)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create tables, recover stale jobs, and run the outbox poll loop."""
    # Activate the tracing SDK if NOTES_API_TRACING is set; a no-op otherwise, so
    # the enrichment task's spans stay inert unless observability is opted in.
    setup_tracing()
    Base.metadata.create_all(bind=engine)
    recover_stale_jobs()
    stop = asyncio.Event()
    loop_task = asyncio.create_task(_run_outbox_loop(stop), name="enrichment-outbox")
    try:
        yield
    finally:
        stop.set()
        loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await loop_task


app = FastAPI(title="Notes API", version="2.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Does not touch the database, so it stays cheap and fast."""
    return {"status": "ok"}
