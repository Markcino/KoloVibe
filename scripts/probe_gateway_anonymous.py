"""Send credential-less requests to every gateway route (local profile, every capability on) and print JSON.

Used by tests only. Each internal-service call is replaced by a recorder, so the output shows both the HTTP status
an anonymous caller receives and whether the request reached any internal service. No network or database is used.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_UUID = "123e4567-e89b-42d3-a456-426614174000"
METHODS = ("get", "post", "put", "patch", "delete")


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
                      KOLOVIBE_LOCAL_POINTS_ENABLED="1", KOLOVIBE_LOCAL_MODERATION_ENABLED="1",
                      KOLOVIBE_LOCAL_BUSINESS_ENABLED="1")
    import django

    django.setup()
    from django.test import Client
    from django.urls import get_resolver

    reached = []

    def record(audience, path, *args, **kwargs):
        reached.append((audience, path))
        raise ConnectionError("blocked by the anonymous-access probe")

    for name, module in list(sys.modules.items()):
        if name.startswith("service") and hasattr(module, "signed_internal_request"):
            module.signed_internal_request = record

    client = Client(raise_request_exception=False)
    routes = {}
    for text in sorted(set(flatten(get_resolver().url_patterns))):
        path = "/" + re.sub(r"<[a-z]+:[a-z_]+>", SAMPLE_UUID, text)
        key = "/" + re.sub(r"<[a-z]+:[a-z_]+>", "{id}", text)
        results = {}
        for method in METHODS:
            before = len(reached)
            response = getattr(client, method)(path, data="{}", content_type="application/json") \
                if method != "get" else client.get(path)
            results[method.upper()] = {"status": response.status_code, "internal_calls": len(reached) - before}
        routes[key] = results
    print(json.dumps(routes))


if __name__ == "__main__":
    main()
