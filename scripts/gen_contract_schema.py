"""Generate the published GET /notes read contract from the live response model.

notes-api is the **provider** on the SYS-006 seam (`kb-agent` reads notes to ground
its RAG answers), so per SYS-018 it owns that contract and publishes it as a
committed artifact consumers assert against. Generated from ``NoteResponse`` —
never hand-edited, so it cannot describe a shape the service does not return.

**This contract is deliberately OPEN, unlike /classify.** `additionalProperties`
is not set to false, because the consumer reads a *subset*: `kb-agent` pulls
`id`, `title`, `content` and `tags` and ignores the rest. Adding a field to
`NoteResponse` is therefore backward-compatible and must not fail anyone's build.
What breaks a consumer is a field it reads being **removed or renamed** — and
because `kb-agent` parses with `.get()`, that failure is silent: notes come back
with `None` titles rather than an error. Silent degradation is exactly what a
contract check is for.

Run locally:
    uv run python scripts/gen_contract_schema.py          # rewrite the artifact
    uv run python scripts/gen_contract_schema.py --check  # exit 1 if stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from notes_api.schemas import NoteResponse  # noqa: E402

CONTRACT_PATH = REPO_ROOT / "contracts" / "notes-read.schema.json"

# Map python/pydantic annotations onto JSON Schema types. Kept explicit rather
# than derived from model_json_schema() so the published contract stays a plain,
# stable shape a consumer can diff, instead of tracking pydantic's output format.
_JSON_TYPES = {
    "int": "integer",
    "str": "string",
    "bool": "boolean",
    "float": "number",
    "datetime": "string",
    "list": "array",
    "dict": "object",
}


def _json_type(annotation: object) -> str:
    """Best-effort JSON Schema type for a model field annotation.

    Handles the three shapes this model uses: a bare class (``int``), a
    parameterised generic (``list[str]``), and an optional union
    (``datetime | None``). Unknown annotations fall back to ``string`` rather
    than raising — the field set is what consumers diff on, and a wrong *type*
    on a field that still exists is a far smaller problem than a crash in the
    generator that stops the artifact being published at all.
    """
    # Optional union: take the non-None arm.
    args = getattr(annotation, "__args__", ())
    if args:
        non_none = [a for a in args if a is not type(None)]  # noqa: E721
        if len(non_none) == 1 and getattr(annotation, "__origin__", None) is not list:
            annotation = non_none[0]

    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        return _JSON_TYPES.get(getattr(origin, "__name__", ""), "string")

    name = getattr(annotation, "__name__", str(annotation))
    return _JSON_TYPES.get(name, "string")


def build_schema() -> dict:
    """Build the read contract from the live NoteResponse model."""
    fields = list(NoteResponse.model_fields)
    properties = {
        name: {"type": _json_type(field.annotation)}
        for name, field in NoteResponse.model_fields.items()
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://raw.githubusercontent.com/sanlee-ys/notes-api/"
            "main/contracts/notes-read.schema.json"
        ),
        "title": "GET /notes — 200 response item",
        "description": (
            "The frozen read contract between notes-api (provider) and its "
            "consumers, governed by system/SYS-006 and enforced per SYS-018. "
            "Consumers read a SUBSET of these fields, so ADDING a field is "
            "backward-compatible and this schema is intentionally open. REMOVING "
            "or RENAMING a field a consumer reads is breaking, and because "
            "consumers parse defensively it fails silently rather than loudly — "
            "which is why it is checked in CI rather than trusted."
        ),
        "type": "object",
        # Deliberately NOT false: see the module docstring. Additions are safe.
        "additionalProperties": True,
        "required": fields,
        "properties": properties,
    }


def main() -> int:
    """Write the contract artifact, or verify it is current under ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed artifact is current; do not write.",
    )
    args = parser.parse_args()

    rendered = json.dumps(build_schema(), indent=2) + "\n"

    if args.check:
        if not CONTRACT_PATH.exists():
            print(f"MISSING: {CONTRACT_PATH}", file=sys.stderr)
            return 1
        if CONTRACT_PATH.read_text(encoding="utf-8") != rendered:
            print(
                "STALE: the committed contract does not match NoteResponse.\n"
                "Run: uv run python scripts/gen_contract_schema.py",
                file=sys.stderr,
            )
            return 1
        print("Contract artifact is current.")
        return 0

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {CONTRACT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
