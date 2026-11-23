"""The gateway's one JSON error shape: ``{"detail": <message>}`` with an HTTP status.

Clients and DOC-205 rely on this body for every refusal the gateway itself produces, so it is defined once.
Owning services keep their own error helpers: they are separate deployables and share no application code.
"""
from django.http import JsonResponse


def error_response(detail, status):
    return JsonResponse({"detail": detail}, status=status)
