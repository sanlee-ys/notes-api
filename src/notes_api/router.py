import os
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import NoteRequest, NoteResponse, TagsRequest
from .service import NoteService

router = APIRouter(prefix="/notes", tags=["notes"])

CLASSIFIER_URL = os.getenv("CLASSIFIER_URL", "")


def _classify_and_writeback(note_id: int, content: str, db: Session) -> None:
    """Fire-and-forget: enrich note tags from the classifier. Errors are silenced."""
    if not CLASSIFIER_URL:
        return
    try:
        resp = httpx.post(
            f"{CLASSIFIER_URL}/classify", json={"text": content}, timeout=10.0
        )
        resp.raise_for_status()
        result = resp.json()
        new_tags = [
            t for t in [result.get("category"), result.get("operational_domain")] if t
        ]
        if new_tags:
            service = NoteService(db)
            note = service.get_by_id(note_id)
            merged = list(set(note.tags) | set(new_tags))
            service.set_tags(note_id, TagsRequest(tags=merged))
    except Exception:
        pass


@router.get("", response_model=list[NoteResponse])
def list_notes(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[NoteResponse]:
    return NoteService(db).get_all(q=q, tag=tag)  # type: ignore[return-value]


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)) -> NoteResponse:
    return NoteService(db).get_by_id(note_id)  # type: ignore[return-value]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    req: NoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> NoteResponse:
    note = NoteService(db).create(req)
    background_tasks.add_task(_classify_and_writeback, note.id, note.content, db)
    return note  # type: ignore[return-value]


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int, req: NoteRequest, db: Session = Depends(get_db)
) -> NoteResponse:
    return NoteService(db).update(note_id, req)  # type: ignore[return-value]


@router.put("/{note_id}/tags", response_model=NoteResponse)
def set_tags(
    note_id: int, req: TagsRequest, db: Session = Depends(get_db)
) -> NoteResponse:
    return NoteService(db).set_tags(note_id, req)  # type: ignore[return-value]


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)) -> None:
    NoteService(db).delete(note_id)
