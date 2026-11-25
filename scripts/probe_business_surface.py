"""Print one side of the Business surface as JSON (`gateway` or `business`); used by the reconciliation test only.

The gateway and the Business service are both a Django project called `service`, so each side is read in its own
process. Nothing is sent over a network and no database is opened for writing.

gateway  -> {"routes": [{"path", "operations": {METHOD: operation}}], "operations": {name: {methods, who, verified_email, query}}}
business -> {"operations": {name: {roles, mfa, verified_email, idempotent, budget}}}
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(service):
    directory = ROOT / "services" / service
    sys.path[:0] = [str(directory), str(ROOT / "services")]
    os.chdir(directory)
    os.environ.update(KOLOVIBE_ENV="local", DJANGO_SETTINGS_MODULE="service.settings", DJANGO_SECRET_KEY="x" * 48,
                      KOLOVIBE_LOCAL_BUSINESS_ENABLED="1")
    import django

    django.setup()


def template(pattern):
    """`me/businesses/<uuid:business_id>` -> `/me/businesses/{business_id}` (the contract's spelling)."""
    return "/" + re.sub(r"<(?:uuid|slug):(\w+)>", r"{\1}", str(pattern.pattern)).removeprefix("api/v1/")


def gateway():
    prepare("gateway")
    from django.test import override_settings
    from service import business as module
    from service.routes import business as routes

    with override_settings(ENVIRONMENT="local", LOCAL_BUSINESS_ENABLED=True):
        patterns = routes.patterns()
    found = []
    for pattern in patterns:
        found.append({"path": template(pattern), "operations": dict(pattern.default_args["operations"])})
    flags = {}
    for flag in ("business_owner", "business_discovery", "business_inquiries", "business_reviews", "business_review_admin"):
        with override_settings(ENVIRONMENT="staging", STAGING_CAPABILITIES=frozenset({flag})):
            flags[flag] = sorted(f"{method} {template(pattern)}"
                                 for pattern in routes.patterns() for method in pattern.default_args["operations"])
    with override_settings(ENVIRONMENT="staging", STAGING_CAPABILITIES=frozenset()):
        closed = len(routes.patterns())
    return {"routes": found, "flags": flags, "routes_when_closed": closed,
            "operations": {name: {"methods": list(methods), "who": who, "verified_email": verified, "query": list(query)}
                           for name, (methods, who, verified, query) in module.OPERATIONS.items()}}


def business():
    prepare("business")
    from service.api import OPERATIONS

    return {"operations": {name: {"roles": list(op.roles), "mfa": op.mfa, "verified_email": op.verified_email,
                                  "idempotent": op.idempotent, "budget": op.budget}
                           for name, op in OPERATIONS.items()}}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("gateway", "business"):
        raise SystemExit("Usage: probe_business_surface.py gateway|business")
    print(json.dumps(gateway() if sys.argv[1] == "gateway" else business()))
