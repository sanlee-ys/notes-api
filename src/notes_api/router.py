"""HTTP routes for the notes resource.

Thin layer: each route delegates to ``NoteService`` and stays free of
business logic. Route docstrings surface verbatim in the OpenAPI/Swagger
docs, so they are written for API consumers, not maintainers.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import NoteRequest, NoteResponse, TagsRequest
from .service import NoteService
from .tasks import classify_and_writeback

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteResponse])
def list_notes(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
    db: Session = Depends(get_db),
) -> list[NoteResponse]:
    """List notes, optionally filtered by search text, tag, and date range."""
    return NoteService(db).get_all(  # type: ignore[return-value]
        q=q,
        tag=tag,
        published_after=published_after,
        published_before=published_before,
    )


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)) -> NoteResponse:
    """Fetch a single note by id."""
    return NoteService(db).get_by_id(note_id)  # type: ignore[return-value]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    req: NoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Create a note; classifier tags are added asynchronously after creation."""
    note = NoteService(db).create(req)
    # Fire-and-forget enrichment (SYS-005). No-op unless CLASSIFIER_URL is set.
    background_tasks.add_task(
        classify_and_writeback, note.id, f"{note.title}\n{note.content}"
    )
    return note  # type: ignore[return-value]


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int, req: NoteRequest, db: Session = Depends(get_db)
) -> NoteResponse:
    """Replace a note's title, content, tags, and publication date."""
    return NoteService(db).update(note_id, req)  # type: ignore[return-value]


@router.put("/{note_id}/tags", response_model=NoteResponse)
def set_tags(
    note_id: int, req: TagsRequest, db: Session = Depends(get_db)
) -> NoteResponse:
    """Replace a note's tags without touching its other fields."""
    return NoteService(db).set_tags(note_id, req)  # type: ignore[return-value]


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a note and its tags."""
    NoteService(db).delete(note_id)
