"""Print one service's registered URL paths (local profile, every feature on) as JSON; used by tests only."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_UUID = "123e4567-e89b-42d3-a456-426614174000"


def flatten(patterns, prefix=""):
    for pattern in patterns:
        text = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):
            yield from flatten(pattern.url_patterns, text)
        else:
            yield text


def main(service):
    directory = ROOT / "services" / service
    sys.path[:0] = [str(directory), str(ROOT / "services")]
    os.chdir(directory)
    os.environ.update(KOLOVIBE_ENV="local", DJANGO_SETTINGS_MODULE="service.settings",
                      DJANGO_SECRET_KEY="x" * 48, KOLOVIBE_LOCAL_MEDIA_ENABLED="1",
                      KOLOVIBE_LOCAL_POINTS_ENABLED="1", KOLOVIBE_LOCAL_MODERATION_ENABLED="1")
    import django

    django.setup()
    from django.urls import get_resolver

    routes = []
    for text in flatten(get_resolver().url_patterns):
        text = text.replace("<uuid:", "<").replace("<slug:", "<")
        for name in ("video_id", "creator_id", "account_id", "session_id", "target_id", "entry_id"):
            text = text.replace(f"<{name}>", SAMPLE_UUID)
        text = text.replace("<operation>", "status")
        routes.append("/" + text)
    print(json.dumps(sorted(set(routes))))


if __name__ == "__main__":
    main(sys.argv[1])
