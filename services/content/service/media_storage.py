"""Private Cloudflare R2 access using the AWS CRT SigV4 signer."""

from contextlib import contextmanager
from http.client import HTTPException, HTTPSConnection
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit


MAX_BYTES = 50 * 1024 * 1024
CONTENT_TYPE = "video/mp4"


class StorageUnavailable(Exception):
    pass


class ObjectMissing(Exception):
    pass


class ObjectChanged(Exception):
    pass


def _secret(name):
    try:
        path = Path(os.environ[name])
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("R2 credentials must be private")
        value = path.read_text().strip()
        if len(value) < 16 or any(character.isspace() for character in value):
            raise ValueError("Invalid R2 credential")
        return value
    except (KeyError, OSError, ValueError):
        raise StorageUnavailable from None


def _signed_url(method, key, seconds, headers):
    account = os.environ.get("KOLOVIBE_R2_ACCOUNT_ID", "")
    bucket = os.environ.get("KOLOVIBE_R2_MEDIA_BUCKET", "")
    if (not re.fullmatch(r"[0-9a-f]{32}", account)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket)
            or not re.fullmatch(r"(?:originals/[0-9a-f-]{36}|playback/[0-9a-f-]{36}/[0-9a-f-]{36})\.mp4", key)):
        raise StorageUnavailable
    host = f"{account}.r2.cloudflarestorage.com"
    try:
        from awscrt.auth import (
            AwsCredentialsProvider, AwsSignatureType, AwsSignedBodyValue, AwsSigningConfig, aws_sign_request,
        )
        from awscrt.exceptions import AwsCrtError
        from awscrt.http import HttpHeaders, HttpRequest
    except ImportError:
        raise StorageUnavailable from None
    try:
        credentials = AwsCredentialsProvider.new_static(
            _secret("KOLOVIBE_R2_ACCESS_KEY_FILE"), _secret("KOLOVIBE_R2_SECRET_KEY_FILE"),
        )
        request = HttpRequest(method=method, path=f"/{bucket}/{key}",
                              headers=HttpHeaders([("Host", host), *headers.items()]))
        config = AwsSigningConfig(
            signature_type=AwsSignatureType.HTTP_REQUEST_QUERY_PARAMS, credentials_provider=credentials,
            region="auto", service="s3", use_double_uri_encode=False, should_normalize_uri_path=False,
            signed_body_value=AwsSignedBodyValue.UNSIGNED_PAYLOAD, expiration_in_seconds=seconds,
        )
        signed = aws_sign_request(request, config).result(timeout=5)
        query = parse_qs(urlsplit(signed.path).query)
        signed_headers = set(query["X-Amz-SignedHeaders"][0].split(";"))
        if not {"host", *(name.lower() for name in headers)} <= signed_headers:
            raise ValueError("Required R2 headers were not signed")
        return f"https://{host}{signed.path}"
    except (AwsCrtError, OSError, ValueError, KeyError):
        raise StorageUnavailable from None


def upload_headers(size):
    return {"Content-Type": CONTENT_TYPE, "Content-Length": str(size), "If-None-Match": "*"}


def sign_upload(key, size, seconds):
    return _signed_url("PUT", key, seconds, upload_headers(size))


def sign_playback(key, seconds):
    return _signed_url("GET", key, seconds, {})


@contextmanager
def _request(method, key, headers=None, body=None):
    headers = headers or {}
    target = urlsplit(_signed_url(method, key, 60, headers))
    conn = HTTPSConnection(target.hostname, timeout=10)
    try:
        conn.request(method, f"{target.path}?{target.query}", body=body, headers=headers)
        with conn.getresponse() as response:
            if response.status == 404:
                raise ObjectMissing
            if response.status == 412:
                raise ObjectChanged
            if not 200 <= response.status < 300:
                raise StorageUnavailable
            yield response
    except (HTTPException, OSError, ValueError):
        raise StorageUnavailable from None
    finally:
        conn.close()


def _length(response):
    value = response.getheader("Content-Length", "")
    return int(value) if re.fullmatch(r"[0-9]{1,10}", value) else None


def inspect_upload(key):
    with _request("HEAD", key) as response:
        return _length(response), response.getheader("Content-Type"), response.getheader("ETag")


def download_upload(key, etag, expected_bytes, path):
    with _request("GET", key, {"If-Match": etag}) as response, path.open("wb") as target:
        if _length(response) != expected_bytes or response.getheader("ETag") != etag:
            raise ObjectChanged
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > expected_bytes or count > MAX_BYTES:
                raise ObjectChanged
            target.write(chunk)
        if count != expected_bytes:
            raise ObjectChanged


def put_playback(key, path):
    headers = {"Content-Type": CONTENT_TYPE, "Content-Length": str(path.stat().st_size),
               "Cache-Control": "private, no-store", "If-None-Match": "*"}
    with path.open("rb") as body, _request("PUT", key, headers, body):
        pass
