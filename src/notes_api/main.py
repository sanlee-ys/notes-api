"""FastAPI application entry point: app construction, lifespan, and liveness.

Wires the notes router into the app and creates database tables at startup
via the lifespan hook — sufficient for a single-process app; a migration tool
(e.g. Alembic) would take over table management if the schema ever needs
versioned changes.

Run locally:
    uvicorn notes_api.main:app --host 127.0.0.1 --port 8081
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from .database import Base, engine
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup; nothing to clean up on shutdown."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Notes API", version="2.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Does not touch the database, so it stays cheap and fast."""
    return {"status": "ok"}
