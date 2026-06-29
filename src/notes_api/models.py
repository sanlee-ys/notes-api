from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Note(Base):
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

    @property
    def tags(self) -> list[str]:
        return [t.tag for t in self._tags]

    @tags.setter
    def tags(self, tag_list: list[str]) -> None:
        self._tags = [NoteTag(tag=t) for t in tag_list]


class NoteTag(Base):
    __tablename__ = "note_tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    tag: Mapped[str] = mapped_column(String(50))
    note: Mapped[Note] = relationship("Note", back_populates="_tags")
