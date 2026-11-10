import hmac
import logging
from urllib.error import URLError

from django.conf import settings
from django.db import DatabaseError, connection
from django.db.migrations.exceptions import InconsistentMigrationHistory
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def is_ready():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM internal_request_nonce LIMIT 0")
            cursor.execute("SELECT rolsuper, rolcreatedb, rolcreaterole "
                           "FROM pg_roles WHERE rolname=current_user")
            if cursor.fetchone() != (False, False, False):
                logger.error("Staging database login has privileged role attributes")
                return False
            cursor.execute("SELECT has_schema_privilege(current_user, current_schema(), 'CREATE'), "
                           "has_database_privilege(current_user, current_database(), 'CREATE')")
            if cursor.fetchone() != (False, False):
                logger.error("Staging runtime login must not own migration privileges")
                return False
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            logger.error("Staging database migrations are pending")
            return False
        if settings.KOLOVIBE_SERVICE_NAME == "gateway":
            from service.internal_client import signed_internal_request
            peers = ("content", "creators") + (("identity",) if settings.STAGING_ACCOUNTS else ())
            for peer in peers:
                with signed_internal_request(peer, "/internal/probe", timeout=2) as response:
                    if response.status != 200 or response.read(100) != b'{"status": "ok"}':
                        logger.error("Staging dependent service probe failed")
                        return False
    except (DatabaseError, InconsistentMigrationHistory, OSError, URLError, ValueError):
        logger.error("Staging readiness dependency failed")
        return False
    return True


@require_GET
def readiness(request):
    ready = is_ready()
    return JsonResponse({"status": "ok" if ready else "unavailable"}, status=200 if ready else 503)


@require_GET
def verification(request):
    expected = "Bearer " + settings.STAGING_PROBE_TOKEN
    if not hmac.compare_digest(request.headers.get("Authorization", "").encode(), expected.encode()):
        logger.warning("Rejected staging verification credential")
        return JsonResponse({"detail": "Forbidden"}, status=403)
    return readiness(request)
