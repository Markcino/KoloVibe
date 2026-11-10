from django.conf import settings
from django.urls import path
from django.http import JsonResponse
from .health import liveness

urlpatterns = [
    path("health/live", liveness, name="liveness"),
    path("internal/probe", lambda request: JsonResponse({"status":"ok"}), name="internal-probe"),
]

if settings.LOCAL_MODERATION_ENABLED:
    from .workflow import moderation_workflow

    urlpatterns.append(path("internal/moderation/<slug:operation>", moderation_workflow, name="internal-moderation"))
