"""SQLAlchemy engine, session factory, and the per-request session dependency.

Defaults to a local SQLite file so the app runs with zero setup; point
DATABASE_URL at anything SQLAlchemy speaks to swap backends without code
changes. The ``check_same_thread`` connect arg is applied only for SQLite,
where it is required because FastAPI may serve a request on a different
thread than the one that opened the connection.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notes.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session scoped to a single request.

    FastAPI dependency: opens a session per request and guarantees it is
    closed when the request finishes, even if the handler raises.

    Yields:
        An open SQLAlchemy session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
