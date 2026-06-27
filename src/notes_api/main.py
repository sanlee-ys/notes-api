from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from .database import Base, engine
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Notes API", version="2.0.0", lifespan=lifespan)
app.include_router(router)
