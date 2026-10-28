from django.urls import path
from .health import liveness

urlpatterns = [path("health/live", liveness, name="liveness")]
