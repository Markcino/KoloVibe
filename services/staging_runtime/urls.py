from django.urls import path
from service.urls import urlpatterns as service_urls

from .health import readiness, verification

urlpatterns = [
    path("health/ready", readiness, name="readiness"),
    path("ops/verify", verification, name="staging-verification"),
    path("internal/probe", readiness, name="internal-staging-readiness"),
    *service_urls,
]
