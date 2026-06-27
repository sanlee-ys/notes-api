"""Background enrichment: classify a new note and write labels back as tags.

This implements the writeback half of the SYS-005 classify-and-writeback contract.
The task runs in-process via FastAPI BackgroundTasks (no broker); it calls the
classifier's HTTP `/classify` seam (SYS-004) and writes the predicted labels back
as namespaced tags with replace semantics so reprocessing is idempotent (R1).
"""

import os

import httpx

from .database import SessionLocal
from .schemas import TagsRequest
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


def classify_and_writeback(note_id: int, text: str) -> None:
    """Classify ``text`` and write the labels back to note ``note_id``.

    No-op when ``CLASSIFIER_URL`` is unset (the default in dev/tests). Best-effort:
    a transient classifier failure, or a note deleted before writeback, is swallowed
    — enrichment never surfaces to the caller and never blocks note creation.
    """
    classifier_url = os.getenv("CLASSIFIER_URL", "")
    if not classifier_url:
        return

    try:
        resp = httpx.post(
            f"{classifier_url}/classify", json={"text": text}, timeout=10.0
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception:
        return

    new_tags = classifier_tags(result)
    if not new_tags:
        return

    # Fresh session: the request's session is closed once the response is sent.
    db = SessionLocal()
    try:
        service = NoteService(db)
        note = service.get_by_id(note_id)  # raises 404 if deleted before writeback
        merged = merge_tags(note.tags, new_tags)
        service.set_tags(note_id, TagsRequest(tags=merged))
    except Exception:
        pass
    finally:
        db.close()
