"""Send authenticated requests as each role and MFA state to every gateway route and print JSON; used by tests only.

Identity is simulated (a session for one account with the given role and MFA state). Every other internal-service
call is replaced by a recorder, so the output shows both the status the caller receives and whether the gateway
forwarded the request to a business service (content, creators, moderation, engagement, points, audit).
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_UUID = "123e4567-e89b-42d3-a456-426614174000"
METHODS = ("get", "post", "put", "patch", "delete")
CALLERS = (("viewer", False), ("creator", False), ("moderator", True), ("moderator", False),
           ("administrator", True), ("administrator", False))


class FakeResponse:
    def __init__(self, status, body):
        self.status, self._body = status, json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit=-1):
        return self._body[:limit] if limit and limit > 0 else self._body


def flatten(patterns, prefix=""):
    for pattern in patterns:
        text = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):
            yield from flatten(pattern.url_patterns, text)
        else:
            yield text


def main():
    directory = ROOT / "services" / "gateway"
    sys.path[:0] = [str(directory), str(ROOT / "services")]
    os.chdir(directory)
    os.environ.update(KOLOVIBE_ENV="local", DJANGO_SETTINGS_MODULE="service.settings",
                      DJANGO_SECRET_KEY="x" * 48, KOLOVIBE_LOCAL_MEDIA_ENABLED="1",
                      KOLOVIBE_LOCAL_POINTS_ENABLED="1", KOLOVIBE_LOCAL_MODERATION_ENABLED="1")
    import django

    django.setup()
    from django.test import Client
    from django.urls import get_resolver

    account = str(uuid.uuid4())
    state = {"role": "viewer", "mfa": False}
    reached = []

    def simulate(audience, path, *args, **kwargs):
        if audience == "identity" and path == "/internal/auth/validate":
            return FakeResponse(200, {"user": {"id": account, "email": "caller@example.test",
                                               "display_name": "Caller", "created_at": "2026-01-01T00:00:00+00:00",
                                               "roles": [state["role"]]},
                                      "session_id": str(uuid.uuid4()), "email_verified": True})
        if audience == "identity" and path == "/internal/auth/standing":
            return FakeResponse(200, {"account_id": account, "account_status": "active",
                                      "mfa_verified": state["mfa"], "email_verified": True})
        reached.append(audience)
        raise ConnectionError("blocked by the role probe")

    for name, module in list(sys.modules.items()):
        if name.startswith("service") and hasattr(module, "signed_internal_request"):
            module.signed_internal_request = simulate

    client = Client(raise_request_exception=False, HTTP_AUTHORIZATION="Bearer " + "a" * 40)
    routes = {}
    for text in sorted(set(flatten(get_resolver().url_patterns))):
        path = "/" + re.sub(r"<[a-z]+:[a-z_]+>", SAMPLE_UUID, text)
        key = "/" + re.sub(r"<[a-z]+:[a-z_]+>", "{id}", text)
        by_caller = {}
        for role, mfa in CALLERS:
            state.update(role=role, mfa=mfa)
            results = {}
            for method in METHODS:
                before = len(reached)
                response = getattr(client, method)(path, data="{}", content_type="application/json") \
                    if method != "get" else client.get(path)
                results[method.upper()] = {"status": response.status_code,
                                           "business_calls": len(reached) - before}
            by_caller[f"{role}:{'mfa' if mfa else 'nomfa'}"] = results
        routes[key] = by_caller
    print(json.dumps(routes))


if __name__ == "__main__":
    main()
