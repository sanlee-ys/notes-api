from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .models import Note, NoteTag
from .schemas import NoteRequest, TagsRequest


class NoteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(
        self,
        q: Optional[str] = None,
        tag: Optional[str] = None,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
    ) -> list[Note]:
        query = self.db.query(Note)
        if q:
            q_lower = q.lower()
            query = query.filter(
                or_(
                    func.lower(Note.title).contains(q_lower),
                    func.lower(Note.content).contains(q_lower),
                )
            )
        if tag:
            query = query.join(Note._tags).filter(NoteTag.tag == tag)
        # Date-range filters operate on the article's publication date. Notes with
        # a NULL published_at are excluded from a bounded range (NULL comparisons
        # are never true), which is the intended behavior: an undated note isn't
        # "from 2014."
        if published_after is not None:
            query = query.filter(Note.published_at >= published_after)
        if published_before is not None:
            query = query.filter(Note.published_at <= published_before)
        return query.all()

    def get_by_id(self, note_id: int) -> Note:
        note = self.db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        return note

    def create(self, req: NoteRequest) -> Note:
        note = Note(title=req.title, content=req.content, published_at=req.published_at)
        note.tags = req.tags
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def update(self, note_id: int, req: NoteRequest) -> Note:
        note = self.get_by_id(note_id)
        note.title = req.title
        note.content = req.content
        note.published_at = req.published_at
        note.tags = req.tags
        self.db.commit()
        self.db.refresh(note)
        return note

    def set_tags(self, note_id: int, req: TagsRequest) -> Note:
        note = self.get_by_id(note_id)
        note.tags = req.tags
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete(self, note_id: int) -> None:
        note = self.get_by_id(note_id)
        self.db.delete(note)
        self.db.commit()
