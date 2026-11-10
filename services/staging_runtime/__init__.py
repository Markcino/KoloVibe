"""Shared deployment configuration, without cross-service application imports."""

import json
import os
from pathlib import Path
import re
import ssl

SERVICES = {"gateway", "identity", "content", "creators", "engagement", "points",
            "moderation", "audit"}


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing staging configuration: {name}")
    return value


def file_value(name, *, private=False):
    path = Path(required(name))
    try:
        if private and path.stat().st_mode & 0o077:
            raise RuntimeError(f"Staging secret must be owner-only: {name}")
        value = path.read_text().strip()
    except (OSError, UnicodeError):
        raise RuntimeError(f"Cannot read staging configuration: {name}") from None
    if not value:
        raise RuntimeError(f"Empty staging configuration: {name}")
    return value


def secret(name):
    value = file_value(name, private=True)
    if len(value) < 32 or "\n" in value or "\r" in value:
        raise RuntimeError(f"Invalid staging credential: {name}")
    return value


def json_file(name, *, private=False):
    try:
        value = json.loads(file_value(name, private=private))
    except ValueError:
        raise RuntimeError(f"Invalid staging JSON: {name}") from None
    if not isinstance(value, dict):
        raise RuntimeError(f"Staging configuration must be an object: {name}")
    return value


def configure(settings):
    from urllib.parse import urlsplit

    service = settings["KOLOVIBE_SERVICE_NAME"]
    if required("KOLOVIBE_SERVICE_NAME") != service:
        raise RuntimeError("Staging service identity does not match its image")
    if os.environ.get("DJANGO_DEBUG", "0") != "0":
        raise RuntimeError("DEBUG is forbidden in staging")
    hosts = required("KOLOVIBE_ALLOWED_HOSTS").split(",")
    if any(not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host)
           or host in ("localhost", "testserver") for host in hosts):
        raise RuntimeError("Staging requires exact approved hostnames")
    database = settings["DATABASES"]["default"]
    if database["ENGINE"] != "django.db.backends.postgresql":
        raise RuntimeError("Staging requires TLS PostgreSQL; SQLite is forbidden")
    file_value("KOLOVIBE_DB_PASSWORD_FILE", private=True)
    database["OPTIONS"]["connect_timeout"] = 3
    database["OPTIONS"]["options"] += " -c statement_timeout=2000"
    for name in ("KOLOVIBE_DB_SSLROOTCERT", "KOLOVIBE_INTERNAL_CA_FILE"):
        try:
            ssl.create_default_context(cafile=required(name))
        except (OSError, ssl.SSLError):
            raise RuntimeError(f"Invalid staging CA: {name}") from None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    file_value("KOLOVIBE_TLS_KEY_FILE", private=True)
    try:
        context.load_cert_chain(required("KOLOVIBE_TLS_CERT_FILE"),
                                required("KOLOVIBE_TLS_KEY_FILE"))
    except (OSError, ssl.SSLError):
        raise RuntimeError("Invalid staging server certificate/key") from None
    callers = json_file("KOLOVIBE_CALLER_KEYS_FILE", private=True)
    if any(name not in SERVICES or not isinstance(key, str) or len(key) < 32
           for name, key in callers.items()):
        raise RuntimeError("Invalid staging caller credentials")
    if service in ("identity", "content", "creators") and "gateway" not in callers:
        raise RuntimeError("Staging peer requires an approved gateway credential")
    settings["STAGING_PROBE_TOKEN"] = secret("KOLOVIBE_PROBE_TOKEN_FILE")
    enabled = os.environ.get("KOLOVIBE_STAGING_ACCOUNTS", "0")
    if enabled not in ("0", "1"):
        raise RuntimeError("Invalid staging account capability")
    accounts = enabled == "1"
    settings["STAGING_ACCOUNTS"] = accounts
    privileged = os.environ.get("KOLOVIBE_STAGING_PRIVILEGED", "0")
    if privileged not in ("0", "1"):
        raise RuntimeError("Invalid privileged capability")
    settings["STAGING_PRIVILEGED"] = privileged == "1"
    if privileged == "1" and (not accounts or service not in ("gateway", "identity")):
        raise RuntimeError("Privileged capability requires approved account services")
    creator_onboarding = os.environ.get("KOLOVIBE_STAGING_CREATOR_ONBOARDING", "0")
    if creator_onboarding not in ("0", "1"):
        raise RuntimeError("Invalid staging creator onboarding capability")
    settings["STAGING_CREATOR_ONBOARDING"] = creator_onboarding == "1"
    if creator_onboarding == "1" and (
        service not in ("gateway", "creators") or service == "gateway" and privileged != "1"
    ):
        raise RuntimeError("Creator onboarding requires the approved creator service and an MFA-enabled gateway")
    if accounts:
        if service not in ("gateway", "identity"):
            raise RuntimeError("Account capability belongs only to gateway/identity")
        approvals = json_file("KOLOVIBE_ACCOUNT_APPROVAL_FILE")
        if any(not isinstance(approvals.get(name), str) or not approvals[name].strip()
               for name in ("identity", "smtp", "credentials", "transport")):
            raise RuntimeError("Staging accounts require recorded approval references")
        if service == "identity":
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                port = int(required("KOLOVIBE_SMTP_PORT"))
                validate_email(required("KOLOVIBE_FROM_EMAIL"))
                if not 1 <= port <= 65535:
                    raise ValueError("Invalid SMTP port")
                host = required("KOLOVIBE_SMTP_HOST")
                if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host):
                    raise ValueError("Invalid SMTP host")
            except (ValueError, ValidationError):
                raise RuntimeError("Invalid approved SMTP port/from address") from None
            settings.update(
                EMAIL_HOST=host,
                EMAIL_PORT=port,
                EMAIL_HOST_USER=file_value("KOLOVIBE_SMTP_USER_FILE", private=True),
                EMAIL_HOST_PASSWORD=file_value("KOLOVIBE_SMTP_PASSWORD_FILE", private=True),
                DEFAULT_FROM_EMAIL=required("KOLOVIBE_FROM_EMAIL"),
                EMAIL_TIMEOUT=5,
                EMAIL_BACKEND="service.mail.VerifiedSMTPBackend",
                EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
            )
            if os.environ.get("KOLOVIBE_SMTP_CA_FILE"):
                try:
                    ssl.create_default_context(cafile=required("KOLOVIBE_SMTP_CA_FILE"))
                except (OSError, ssl.SSLError):
                    raise RuntimeError("Invalid SMTP trust configuration") from None
        if privileged == "1":
            if any(not isinstance(approvals.get(name), str) or not approvals[name].strip()
                   for name in ("mfa", "audit")):
                raise RuntimeError("Privileged sessions require MFA/audit approval references")
            if service == "identity":
                from cryptography.fernet import Fernet
                try:
                    Fernet(file_value("KOLOVIBE_MFA_ENCRYPTION_KEY_FILE", private=True).encode())
                except ValueError:
                    raise RuntimeError("Invalid MFA encryption credential") from None
                secret("KOLOVIBE_OUTBOUND_KEY_FILE")
                audit_peers = json_file("KOLOVIBE_TRUSTED_PEERS_FILE")
                if set(audit_peers) != {"audit"}:
                    raise RuntimeError("Identity requires the approved audit destination")
                if not isinstance(audit_peers["audit"], str):
                    raise RuntimeError("Invalid audit destination")
                try:
                    audit_url = urlsplit(audit_peers["audit"])
                    audit_url.port
                except ValueError:
                    raise RuntimeError("Invalid audit destination") from None
                if (audit_url.scheme != "https" or not audit_url.hostname or audit_url.username
                        or audit_url.password or audit_url.path not in ("", "/")
                        or audit_url.query or audit_url.fragment):
                    raise RuntimeError("Identity audit destination must use verified HTTPS")
    if service == "gateway":
        secret("KOLOVIBE_OUTBOUND_KEY_FILE")
        peers = json_file("KOLOVIBE_TRUSTED_PEERS_FILE")
        expected = {"content", "creators"} | ({"identity"} if accounts else set())
        if set(peers) != expected:
            raise RuntimeError("Staging peers must match the enabled capabilities")
        for origin in peers.values():
            if not isinstance(origin, str):
                raise RuntimeError("Invalid staging peer origin")
            try:
                url = urlsplit(origin)
                url.port
            except ValueError:
                raise RuntimeError("Invalid staging peer origin") from None
            if (url.scheme != "https" or not url.hostname or url.username
                    or url.password or url.path not in ("", "/")
                    or url.query or url.fragment):
                raise RuntimeError("Staging peers require canonical HTTPS origins")
    settings.update(
        DEBUG=False, ALLOWED_HOSTS=hosts, ROOT_URLCONF="staging_runtime.urls",
        SECURE_SSL_REDIRECT=True, SECURE_HSTS_SECONDS=3600,
        SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
        SECURE_CONTENT_TYPE_NOSNIFF=True, X_FRAME_OPTIONS="DENY",
        DATA_UPLOAD_MAX_MEMORY_SIZE=8192,
    )
    # Cookie-free APIs use bearer/HMAC auth; web CSRF stays in the web app.
    # A restricted pilot must not claim domain-wide HSTS/preload approval.
    settings["SILENCED_SYSTEM_CHECKS"] = ["security.W003", "security.W005", "security.W021"]
    settings["MIDDLEWARE"] = [
        "staging_runtime.middleware.RestrictedStagingMiddleware",
        *settings["MIDDLEWARE"],
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ]
