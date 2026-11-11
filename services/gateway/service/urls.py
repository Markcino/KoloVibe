"""Gateway URL table composed from per-domain route modules behind capability gates."""
from .routes import catalog, creator_studio, engagement, identity, moderation, points

urlpatterns = [
    *catalog.patterns(),
    *identity.patterns(),
    *creator_studio.patterns(),
    *engagement.patterns(),
    *moderation.patterns(),
    *points.patterns(),
]
