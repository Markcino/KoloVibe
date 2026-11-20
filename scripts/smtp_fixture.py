"""Bounded loopback STARTTLS mail capture; never relays or contacts external mail."""

from contextlib import contextmanager
import base64
import binascii
from email import policy
from email.parser import BytesParser
import socketserver
import ssl
import hmac
import re
from threading import Thread

from test_postgres_foundations import secret_file


def mailed_code(base):
    """The six-digit code in the captured verification or reset email (ADR-013 amendment A-1)."""
    found = re.search(r": ([0-9]{6})(?:\n|$)", (base / "verification-mail").read_text())
    if found is None:
        raise AssertionError("The captured email carries no six-digit code")
    return found.group(1)


@contextmanager
def smtp_fixture(base):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(base / "server.crt", base / "server.key")

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            sock = self.request
            sock.settimeout(5)
            reader = sock.makefile("rb")
            tls = False
            authenticated = False
            sock.sendall(b"220 localhost fixture SMTP\r\n")
            try:
                for _ in range(50):
                    line = reader.readline(4097)
                    if not line or len(line) > 4096:
                        break
                    verb = line.split(b" ", 1)[0].strip().upper()
                    if verb in (b"EHLO", b"HELO"):
                        sock.sendall(b"250-localhost\r\n250-AUTH PLAIN\r\n250 OK\r\n"
                                     if tls else b"250-localhost\r\n250 STARTTLS\r\n")
                    elif verb == b"STARTTLS" and not tls:
                        sock.sendall(b"220 Begin TLS\r\n")
                        reader.close()
                        sock = context.wrap_socket(sock, server_side=True)
                        reader = sock.makefile("rb")
                        tls = True
                    elif verb == b"AUTH" and tls:
                        try:
                            fields = line.strip().split()
                            credentials = base64.b64decode(fields[2], validate=True).split(b"\0")
                            authenticated = (fields[1] == b"PLAIN" and len(credentials) == 3
                                and hmac.compare_digest(credentials[1], (base / "smtp-user").read_bytes())
                                and hmac.compare_digest(credentials[2], (base / "smtp-password").read_bytes()))
                        except (IndexError, binascii.Error):
                            authenticated = False
                        sock.sendall(b"235 Authenticated\r\n" if authenticated else b"535 Rejected\r\n")
                    elif verb in (b"MAIL", b"RCPT") and authenticated:
                        sock.sendall(b"250 OK\r\n")
                    elif verb == b"DATA" and authenticated:
                        sock.sendall(b"354 End with dot\r\n")
                        chunks = []
                        size = 0
                        while True:
                            chunk = reader.readline(4097)
                            if chunk == b".\r\n":
                                break
                            if not chunk or len(chunk) > 4096 or size > 16384:
                                raise ValueError("Oversized fixture mail")
                            size += len(chunk)
                            chunks.append(chunk)
                        message = BytesParser(policy=policy.default).parsebytes(b"".join(chunks))
                        secret_file(base / "verification-mail", message.get_content().strip())
                        sock.sendall(b"250 Captured privately\r\n")
                    elif verb == b"QUIT":
                        sock.sendall(b"221 Bye\r\n")
                        break
                    else:
                        sock.sendall(b"530 TLS authentication required\r\n")
            finally:
                reader.close()
                sock.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True

    server = Server(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
