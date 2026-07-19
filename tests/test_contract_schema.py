"""The published GET /notes contract must match what the service actually returns.

notes-api is the provider on the SYS-006 seam and owns that contract;
``contracts/notes-read.schema.json`` is the artifact consumers assert against, so
its one job is to never describe a shape this service does not return.

The asymmetry with `/classify` is deliberate and tested here. That contract is
*closed* — every consumer must read every field, so an addition is breaking. This
one is *open*, because `kb-agent` reads a subset (`id`, `title`, `content`,
`tags`) and ignores the rest. Adding a field to ``NoteResponse`` is
backward-compatible and must not redden anyone's build. What breaks a consumer is
a field it reads being removed or renamed — and since consumers parse with
``.get()``, that degrades silently to ``None`` rather than raising. Silent
degradation is the reason this is checked rather than trusted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from gen_contract_schema import CONTRACT_PATH, build_schema  # noqa: E402

from notes_api.schemas import NoteResponse  # noqa: E402

# The fields kb-agent's search_notes actually parses, verified against
# kb-agent/agent/tools.py. If one of these disappears from NoteResponse, that
# consumer silently returns notes with None values rather than failing.
CONSUMER_READS = ("id", "title", "content", "tags")


def _committed() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_committed_artifact_exists():
    assert CONTRACT_PATH.exists(), (
        f"{CONTRACT_PATH} is missing. Consumers fetch this file; without it the "
        "seam has no guard. Run: uv run python scripts/gen_contract_schema.py"
    )


def test_committed_artifact_is_not_stale():
    """Edit NoteResponse, forget to regenerate, and this fails."""
    rendered = json.dumps(build_schema(), indent=2) + "\n"
    assert CONTRACT_PATH.read_text(encoding="utf-8") == rendered, (
        "The committed contract is stale relative to NoteResponse.\n"
        "Run: uv run python scripts/gen_contract_schema.py"
    )


def test_required_fields_match_the_response_model():
    assert _committed()["required"] == list(NoteResponse.model_fields)


def test_contract_is_open_on_purpose():
    """Additions are backward-compatible here; closing this would be wrong.

    Pinned as a test because "closed is safer" is a tempting and, for this seam,
    incorrect edit — it would fail every consumer build on a purely additive
    provider change.
    """
    assert _committed()["additionalProperties"] is True


def test_every_field_a_consumer_reads_is_present():
    """The fields kb-agent depends on must survive.

    This is the assertion that actually protects the seam: removing one of these
    degrades that consumer silently, since it parses with .get().
    """
    required = _committed()["required"]
    missing = [f for f in CONSUMER_READS if f not in required]
    assert not missing, (
        f"NoteResponse no longer carries {missing}, which kb-agent's search_notes "
        f"reads. That consumer will return None for those fields rather than "
        f"failing, so nothing will look broken until an answer is wrong."
    )


def test_scalar_types_are_mapped_not_defaulted():
    """A guard against the type mapper silently falling back to 'string'.

    `id` is the canary: it is the only non-string scalar, so if the annotation
    mapper regresses it is the first field to go wrong.
    """
    props = _committed()["properties"]
    assert props["id"]["type"] == "integer"
    assert props["tags"]["type"] == "array"
