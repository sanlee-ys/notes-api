"""SQLAlchemy ORM models: notes, tags, and the enrichment outbox.

Tags live in a child table (one row per tag) rather than a delimited string
column, so tag filtering is a real SQL join instead of substring matching.
The ``Note.tags`` property hides that shape: callers read and write plain
``list[str]`` and the relationship bookkeeping stays in this module.

``EnrichmentJob`` is the durable outbox for classify-and-writeback (ADR-003).
A queued row survives a process crash; FastAPI BackgroundTasks is only the
same-process kick that drains due jobs after the HTTP response.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Note(Base):
    """A stored note, with its tags and async-enrichment bookkeeping."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # The article's own publication date — distinct from created_at (when the note
    # was saved). Nullable: a free-form note has no publication date. This is what
    # makes "show me everything from 2014" a real query instead of a substring match.
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    # Tracks whether the async classifier enrichment task has run.
    # pending → done (classifier wrote tags back) or failed (classifier error).
    # When CLASSIFIER_URL is unset (dev/test), this stays "pending" indefinitely.
    enrichment_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    _tags: Mapped[list[NoteTag]] = relationship(
        "NoteTag", back_populates="note", cascade="all, delete-orphan", lazy="joined"
    )
    # ORM cascade so a note delete removes outbox rows even when SQLite is not
    # enforcing FOREIGN KEY pragmas. Not joined: list/get must not load jobs.
    _enrichment_jobs: Mapped[list[EnrichmentJob]] = relationship(
        "EnrichmentJob",
        back_populates="note",
        cascade="all, delete-orphan",
    )

    @property
    def tags(self) -> list[str]:
        """Return this note's tags as a plain list of strings."""
        return [t.tag for t in self._tags]

    @tags.setter
    def tags(self, tag_list: list[str]) -> None:
        """Replace all tags with a fresh set of NoteTag rows."""
        self._tags = [NoteTag(tag=t) for t in tag_list]


class EnrichmentJob(Base):
    """One classify-and-writeback job for one note.

    Status is ``queued``, ``running``, ``done``, or ``failed``. ``available_at``
    is the claim lease: a due ``queued`` or crashed ``running`` row may be
    claimed. Payload is the title-plus-content snapshot from create time.
    """

    __tablename__ = "enrichment_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    payload_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    available_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    note: Mapped[Note] = relationship("Note", back_populates="_enrichment_jobs")


class NoteTag(Base):
    """One tag on one note; rows are cascade-deleted with their note."""

    __tablename__ = "note_tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    tag: Mapped[str] = mapped_column(String(50))
    note: Mapped[Note] = relationship("Note", back_populates="_tags")
