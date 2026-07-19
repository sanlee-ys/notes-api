"""Assert this consumer still matches the provider's published /classify contract.

notes-api is the **second consumer** on the SYS-004 seam (the first is `kb-agent`):
the enrichment BackgroundTask POSTs to the classifier's `/classify` endpoint and
encodes the response as namespaced tags. That makes this repo subject to the same
drift failure, and it hit — the classifier shipped `region` in v3.0.0 and this
service quietly dropped the field for a day while every test stayed green.

Per [SYS-018] the provider owns and publishes the contract; each consumer fetches
it in CI and fails on divergence. This is that check. It is the only thing in this
repo that looks outward — everything else asserts this code against fixtures this
repo controls, which is precisely why the drift was invisible here.

Failure policy (matches kb-agent's, deliberately):

* **Divergence** (fetch succeeded, shapes differ) -> exit 1. The real guard.
* **Fetch failure** (network, DNS, timeout, non-200) -> exit 0 with a loud
  warning. A GitHub outage must not redden an unrelated build; the cost is that a
  genuine outage reads as a pass, so the warning is explicit rather than swallowed.

Run locally:
    uv run python scripts/check_classify_contract.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from notes_api.tasks import CLASSIFY_FIELD_TAGS  # noqa: E402

CONTRACT_URL = (
    "https://raw.githubusercontent.com/sanlee-ys/defense-news-classifier/"
    "main/contracts/classify-response.schema.json"
)
TIMEOUT_SECONDS = 15


def fetch_contract(url: str = CONTRACT_URL) -> dict | None:
    """Fetch the provider's published contract, or None if it is unreachable.

    Returns:
        The parsed schema, or ``None`` when it could not be fetched or parsed —
        the caller treats that as a warning, not a failure.
    """
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(
                "WARNING: the provider has not published "
                "contracts/classify-response.schema.json on main.\n"
                "         This check is INERT until it does.",
                file=sys.stderr,
            )
        else:
            print(f"WARNING: HTTP {exc.code} fetching the contract.", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"WARNING: could not fetch or parse the contract: {exc}", file=sys.stderr)
        return None


def compare(schema: dict) -> list[str]:
    """Compare this consumer's mapped fields against the published contract.

    Unlike a strict shape check, this consumer is *allowed* to ignore provider
    fields it has not adopted yet — dropping an unmapped field is deliberate
    tolerance (see ``classifier_tags``). What must never happen silently is the
    provider gaining a field nobody notices, so an unmapped provider field is
    reported as drift requiring an explicit decision.

    Returns:
        A list of human-readable problems; empty means the shapes agree.
    """
    problems: list[str] = []

    published = schema.get("required")
    if not isinstance(published, list):
        return ["The published contract has no 'required' list — cannot compare."]

    ours = list(CLASSIFY_FIELD_TAGS)

    unmapped = [f for f in published if f not in ours]
    if unmapped:
        problems.append(
            f"The provider now returns {unmapped}, which this service does not "
            f"map to a tag.\n"
            f"  provider requires : {published}\n"
            f"  this consumer maps: {ours}\n"
            f"  Add it to CLASSIFY_FIELD_TAGS (which also extends "
            f"CLASSIFIER_PREFIXES, keeping replace-semantics correct), or record "
            f"a deliberate decision not to."
        )

    stale = [f for f in ours if f not in published]
    if stale:
        problems.append(
            f"This service maps {stale}, which the provider no longer returns. "
            f"Those tags will silently stop being written."
        )

    if schema.get("additionalProperties") is not False:
        problems.append(
            "The published contract is no longer closed "
            "(additionalProperties is not false), so an added provider field "
            "would stop being detectable."
        )

    return problems


def main() -> int:
    """Fetch the published contract and fail on divergence."""
    schema = fetch_contract()
    if schema is None:
        print("Contract check SKIPPED (see warning above).")
        return 0

    problems = compare(schema)
    if problems:
        print("SYS-004 CONTRACT DRIFT — this consumer no longer matches the provider:")
        for problem in problems:
            print(f"\n{problem}")
        print(
            f"\nPublished contract: {CONTRACT_URL}\n"
            "This is the failure mode SYS-018 exists to make loud. Do not silence "
            "this check; update the consumer."
        )
        return 1

    mapped = list(CLASSIFY_FIELD_TAGS)
    print(f"Contract OK — consumer maps every published field {mapped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
