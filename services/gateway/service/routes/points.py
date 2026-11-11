"""Creator-owned points reads and server-qualified watch tracking routes."""
from django.urls import path

from ..capabilities import enabled


def patterns():
    routes = []
    if enabled("points"):
        from ..pilot_points import creator_points

        routes += [
            path("api/v1/creators/me/points", creator_points, {"operation": "balance"}, name="creator-points"),
            path("api/v1/creators/me/points/entries", creator_points, {"operation": "entries"},
                 name="creator-points-entries"),
            path("api/v1/creators/me/points/entries/<uuid:entry_id>", creator_points,
                 {"operation": "entry"}, name="creator-points-entry"),
        ]
    if enabled("watch"):
        from ..pilot_points import watch

        routes += [
            path("api/v1/videos/<uuid:video_id>/watch-sessions", watch, name="create-watch-session"),
            path("api/v1/engagement/watch-events", watch, name="submit-watch-progress"),
        ]
    return routes
