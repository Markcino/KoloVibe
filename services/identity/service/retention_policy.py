"""Which retained evidence is compatible with a completed erasure (Decision C, ADR-020, RV2-04, #136).

Each participating service reports the categories it kept. By default every retained category keeps the request
`processing`. An owner-approved retention policy may name evidence categories that may stay, legally retained and
de-identified from the account, while the request completes. The values are the owner's (with counsel) decision: this
module ships none and invents none.

The policy is a JSON file named by `KOLOVIBE_ERASURE_RETENTION_POLICY_FILE`:

    {"policy_id": "ADR-020-v1", "status": "approved", "approved_by": "<owner>", "approved_on": "YYYY-MM-DD",
     "reference": "<decision record>", "compatible": {"content": ["audit_events"], ...}}

- Only categories in `EVIDENCE_CATEGORIES` may be named; a typo or an unknown category refuses the whole file.
- `NEVER_COMPATIBLE` categories are not evidence but unfinished work (an owned business, media the worker could not
  remove). No policy can let a request complete over them.
- `status` "sandbox" is accepted only in local development and tests, for clearly labelled fixtures.
- A missing, unreadable or invalid file means the empty policy, so nothing completes over a retained category.
"""
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# What each service can report as retained evidence (services/<service>/service/privacy.py).
EVIDENCE_CATEGORIES = {
    "engagement": frozenset({"qualified_watches", "fraud_holds"}),
    "creators": frozenset({"measures", "appeals", "audit_events"}),
    "moderation": frozenset({"copyright_claims", "cited_report_details", "counter_notices", "appeals", "decisions",
                             "edit_decisions", "strikes", "staff_decisions", "staff_edit_decisions", "audit_events"}),
    "content": frozenset({"attestations", "prescreen_results", "copyright_claims", "rights_events", "fingerprints",
                          "screening_records", "source_digests", "moderation_receipts", "audit_events"}),
    "business": frozenset({"reviews", "inquiries", "inquiry_messages", "inquiry_blocks", "verification_evidence",
                           "verification_decisions", "profile_revisions", "audit_events"}),
}
NEVER_COMPATIBLE = {"business": frozenset({"business_ownership"}), "content": frozenset({"untracked_media"})}
FIELDS = {"policy_id", "status", "approved_by", "approved_on", "reference", "compatible"}
EMPTY = {"policy_id": "", "compatible": {}}


class InvalidPolicy(ValueError):
    pass


def parse(text, *, environment):
    try:
        policy = json.loads(text)
    except ValueError:
        raise InvalidPolicy("not JSON") from None
    if not isinstance(policy, dict) or set(policy) != FIELDS:
        raise InvalidPolicy("unexpected fields")
    if not isinstance(policy["policy_id"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", policy["policy_id"]):
        raise InvalidPolicy("policy_id")
    if policy["status"] not in ("approved", "sandbox"):
        raise InvalidPolicy("status")
    if policy["status"] == "sandbox" and environment not in ("local", "test"):
        raise InvalidPolicy("a sandbox policy is refused outside local development and tests")
    for field in ("approved_by", "reference"):
        if not isinstance(policy[field], str) or not policy[field].strip() or len(policy[field]) > 200:
            raise InvalidPolicy(field)
    if not isinstance(policy["approved_on"], str) or not re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]",
                                                                        policy["approved_on"]):
        raise InvalidPolicy("approved_on")
    compatible = policy["compatible"]
    if not isinstance(compatible, dict) or set(compatible) - set(EVIDENCE_CATEGORIES):
        raise InvalidPolicy("compatible must be keyed by participating service")
    for service, names in compatible.items():
        if (not isinstance(names, list) or len(set(names)) != len(names)
                or any(not isinstance(name, str) or name not in EVIDENCE_CATEGORIES[service] for name in names)):
            raise InvalidPolicy("compatible names a category that is not that service's retained evidence")
    return {"policy_id": policy["policy_id"],
            "compatible": {service: frozenset(names) for service, names in compatible.items()}}


def current():
    """The configured policy, or the empty policy when none is configured or it is invalid (logged, never raised)."""
    path = os.environ.get("KOLOVIBE_ERASURE_RETENTION_POLICY_FILE", "")
    if not path:
        return EMPTY
    environment = os.environ.get("KOLOVIBE_ENV", "")
    try:
        return parse(Path(path).read_text(), environment=environment)
    except (OSError, UnicodeDecodeError, InvalidPolicy) as error:
        reason = error.args[0] if isinstance(error, InvalidPolicy) else type(error).__name__
        logger.error("Erasure retention policy refused (%s); retained categories keep requests processing", reason)
        return EMPTY


def blocking(service, retained, policy):
    """The retained categories that still keep a request processing under this policy."""
    allowed = policy["compatible"].get(service, frozenset())
    return [name for name in retained if name in NEVER_COMPATIBLE.get(service, ()) or name not in allowed]
