"""Background enrichment: classify a new note and write labels back as tags.

This implements the writeback half of the SYS-005 classify-and-writeback contract.
The task runs in-process via FastAPI BackgroundTasks (no broker); it calls the
classifier's HTTP `/classify` seam (SYS-004) and writes the predicted labels back
as namespaced tags with replace semantics so reprocessing is idempotent (R1).

Enrichment status lifecycle:
  pending → done   (classifier returned labels and they were written back)
  pending → failed (classifier error, unreachable, or returned no labels)

When CLASSIFIER_URL is unset (dev/test), the task is a no-op and status stays
"pending" — that signals "not configured" rather than "failed."
"""

import os

import httpx

from .database import SessionLocal
from .models import Note
from .service import NoteService

# Classifier-owned tags are namespaced so the writeback can replace only its own
# prior tags on reprocessing, never a user's hand-applied tags (SYS-005).
CLASSIFIER_PREFIXES = ("category:", "domain:")
TAG_CAP = 20


def classifier_tags(result: dict[str, str]) -> list[str]:
    """Encode the classifier's two-field response as namespaced tags."""
    tags: list[str] = []
    category = result.get("category")
    domain = result.get("operational_domain")
    if category:
        tags.append(f"category:{category}")
    if domain:
        tags.append(f"domain:{domain}")
    return tags


def merge_tags(
    existing: list[str], new_classifier_tags: list[str], cap: int = TAG_CAP
) -> list[str]:
    """Merge fresh classifier tags into a note's existing tags (SYS-005).

    User tags are preserved; the task's own prior classifier tags (namespaced)
    are dropped and replaced — so reprocessing converges instead of accumulating.
    Capped at ``cap``: the classifier tags always land; the oldest user tags are
    dropped from this snapshot if the note is already at the cap.
    """
    user_tags = [t for t in existing if not t.startswith(CLASSIFIER_PREFIXES)]
    room = max(cap - len(new_classifier_tags), 0)
    kept_user = user_tags[-room:] if room else []
    return kept_user + new_classifier_tags


def _write_enrichment_status(note_id: int, status: str) -> None:
    """Persist enrichment_status on a note. Best-effort: never raises."""
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            note.enrichment_status = status
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def classify_and_writeback(note_id: int, text: str) -> None:
    """Classify ``text`` and write the labels back to note ``note_id``.

    No-op when ``CLASSIFIER_URL`` is unset (the default in dev/tests). On
    classifier failure, writes ``enrichment_status="failed"`` to the note so
    callers can see the enrichment didn't land. On success, writes the classifier
    tags back and sets ``enrichment_status="done"``.
    """
    classifier_url = os.getenv("CLASSIFIER_URL", "")
    if not classifier_url:
        return  # Not configured — leave status as "pending" (not a failure).

    try:
        resp = httpx.post(
            f"{classifier_url}/classify", json={"text": text}, timeout=10.0
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception:
        _write_enrichment_status(note_id, "failed")
        return

    new_tags = classifier_tags(result)
    if not new_tags:
        _write_enrichment_status(note_id, "failed")
        return

    # Fresh session: the request's session is closed once the response is sent.
    db = SessionLocal()
    try:
        service = NoteService(db)
        note = service.get_by_id(note_id)  # raises 404 if deleted before writeback
        merged = merge_tags(note.tags, new_tags)
        note.tags = merged
        note.enrichment_status = "done"
        db.commit()
    except Exception:
        pass  # Note deleted before writeback — not a failure we can surface.
    finally:
        db.close()
