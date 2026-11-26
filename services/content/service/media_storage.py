"""Private Cloudflare R2 access with a pure-Python SigV4 presigner (scoped keys come from secret files only)."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
from http.client import HTTPException, HTTPSConnection
import os
from pathlib import Path
import re
import ssl
from urllib.parse import quote, urlsplit


MAX_BYTES = 50 * 1024 * 1024
MAX_POSTER_BYTES = 1024 * 1024
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


def _hmac(key, message):
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def _signed_url(method, key, seconds, headers, now=None):
    """SigV4 query-string presigning for R2 in pure Python (no native signer, so the Alpine image can run it).

    Every header the caller names is signed together with `host`, so a client cannot change the content type,
    size or create-only condition of an upload without invalidating the signature. The payload is unsigned
    (`UNSIGNED-PAYLOAD`), which is what a browser or mobile client PUT needs. The result is cross-checked against
    the AWS CRT implementation in the test suite.
    """
    account = os.environ.get("KOLOVIBE_R2_ACCOUNT_ID", "")
    bucket = os.environ.get("KOLOVIBE_R2_MEDIA_BUCKET", "")
    if (not re.fullmatch(r"[0-9a-f]{32}", account)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket)
            or not re.fullmatch(r"(?:originals/[0-9a-f-]{36}\.mp4|playback/[0-9a-f-]{36}/[0-9a-f-]{36}\.(?:mp4|jpg)"
                                r"|posters/[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg)", key)
            or method not in ("GET", "PUT", "HEAD", "DELETE") or not 1 <= seconds <= 604800):
        raise StorageUnavailable
    access, secret = _secret("KOLOVIBE_R2_ACCESS_KEY_FILE"), _secret("KOLOVIBE_R2_SECRET_KEY_FILE")
    host = f"{account}.r2.cloudflarestorage.com"
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp, day = moment.strftime("%Y%m%dT%H%M%SZ"), moment.strftime("%Y%m%d")
    scope = f"{day}/auto/s3/aws4_request"
    signed = {"host": host}
    for name, value in headers.items():
        signed[name.lower()] = " ".join(str(value).split())
    names = sorted(signed)
    query = {"X-Amz-Algorithm": "AWS4-HMAC-SHA256", "X-Amz-Credential": f"{access}/{scope}", "X-Amz-Date": stamp,
             "X-Amz-Expires": str(seconds), "X-Amz-SignedHeaders": ";".join(names)}
    canonical_query = "&".join(f"{quote(name, safe='')}={quote(value, safe='')}" for name, value in sorted(query.items()))
    path = f"/{bucket}/{key}"
    canonical = "\n".join((method, quote(path, safe="/-_.~"), canonical_query,
                          "".join(f"{name}:{signed[name]}\n" for name in names), ";".join(names), "UNSIGNED-PAYLOAD"))
    to_sign = "\n".join(("AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()))
    signing_key = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode(), day), "auto"), "s3"), "aws4_request")
    signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()
    return f"https://{host}{path}?{canonical_query}&X-Amz-Signature={signature}"


def upload_headers(size):
    return {"Content-Type": CONTENT_TYPE, "Content-Length": str(size), "If-None-Match": "*"}


def sign_upload(key, size, seconds):
    return _signed_url("PUT", key, seconds, upload_headers(size))


def sign_playback(key, seconds):
    return _signed_url("GET", key, seconds, {})


def _proxy_endpoint():
    """The validated (host, port) of the restricted R2 egress proxy, or None for direct access (local development only).

    Outside `KOLOVIBE_ENV=local` the proxy is mandatory: an unset or malformed value raises StorageUnavailable
    and the request is never attempted directly. Only a plain `http://host:port` origin is accepted (the proxy
    listens on a private overlay and tunnels with CONNECT); credentials, paths, queries and fragments are refused.
    """
    value = os.environ.get("KOLOVIBE_R2_HTTPS_PROXY", "")
    if not value:
        if os.environ.get("KOLOVIBE_ENV") == "local":
            return None
        raise StorageUnavailable
    try:
        url = urlsplit(value)
        host, port = url.hostname, url.port
        valid = (url.scheme == "http" and host and port and re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host)
                 and not url.username and url.password is None and "@" not in url.netloc
                 and url.path in ("", "/") and not url.query and not url.fragment and "#" not in value
                 and "?" not in value)
    except ValueError:
        valid = False
    if not valid:
        raise StorageUnavailable
    return host, port


def _connection(host):
    """An HTTPS connection to the R2 endpoint, tunnelled through the proxy with CONNECT when one is configured.

    TLS is negotiated end to end with the R2 host over the tunnel, so the certificate and hostname checks apply
    to the original endpoint and the Host header stays the signed one. There is no direct fallback.
    """
    proxy = _proxy_endpoint()
    context = ssl.create_default_context()
    if proxy is None:
        return HTTPSConnection(host, timeout=10, context=context)
    connection = HTTPSConnection(proxy[0], proxy[1], timeout=10, context=context)
    connection.set_tunnel(host, 443)
    return connection


@contextmanager
def _request(method, key, headers=None, body=None):
    headers = headers or {}
    target = urlsplit(_signed_url(method, key, 60, headers))
    conn = _connection(target.hostname)
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
    except (HTTPException, OSError, ValueError, ssl.SSLError):
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


def download_playback(key, path):
    """Stream a private rendition to a local file, bounded by the playback size limit; never signs a public URL."""
    with _request("GET", key) as response, path.open("wb") as target:
        length = _length(response)
        if length is None or not 0 < length <= MAX_BYTES:
            raise StorageUnavailable
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > length:
                raise StorageUnavailable
            target.write(chunk)
        if count != length:
            raise StorageUnavailable


def put_playback(key, path):
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise StorageUnavailable
    headers = {"Content-Type": CONTENT_TYPE, "Content-Length": str(path.stat().st_size),
               "Cache-Control": "private, no-store", "If-None-Match": "*"}
    with path.open("rb") as body, _request("PUT", key, headers, body):
        pass


def put_poster(key, path):
    if not 0 < path.stat().st_size <= MAX_POSTER_BYTES:
        raise StorageUnavailable
    headers = {"Content-Type": "image/jpeg", "Content-Length": str(path.stat().st_size),
               "Cache-Control": "private, no-store", "If-None-Match": "*"}
    with path.open("rb") as body, _request("PUT", key, headers, body):
        pass


def delete_object(key):
    """Remove one private object (Decision C erasure). An object that is already gone counts as removed."""
    try:
        with _request("DELETE", key):
            pass
    except ObjectMissing:
        pass


def read_preview(key):
    """Bounded private MP4 proxy; storage destinations never reach the browser."""
    with _request("GET", key) as response:
        length = _length(response)
        if length is None or not 0 < length <= MAX_BYTES:
            raise StorageUnavailable
        data = response.read(MAX_BYTES + 1)
        if len(data) != length:
            raise StorageUnavailable
        return data
