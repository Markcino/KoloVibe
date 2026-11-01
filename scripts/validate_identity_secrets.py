"""Offline validation; mappings contain variable names, never credentials or mail."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

SECRET_FILES = {
    "KOLOVIBE_IDENTITY_DJANGO_KEY": "DJANGO_SECRET_KEY_FILE",
    "KOLOVIBE_IDENTITY_DB_PASSWORD": "KOLOVIBE_DB_PASSWORD_FILE",  # pragma: allowlist secret
    "KOLOVIBE_IDENTITY_DB_CA": "KOLOVIBE_DB_SSLROOTCERT",
    "KOLOVIBE_IDENTITY_TLS_CERT": "KOLOVIBE_TLS_CERT_FILE",
    "KOLOVIBE_IDENTITY_TLS_KEY": "KOLOVIBE_TLS_KEY_FILE",
    "KOLOVIBE_INTERNAL_CA": "KOLOVIBE_INTERNAL_CA_FILE",
    "KOLOVIBE_IDENTITY_CALLER_KEYS": "KOLOVIBE_CALLER_KEYS_FILE",
    "KOLOVIBE_IDENTITY_PROBE_TOKEN": "KOLOVIBE_PROBE_TOKEN_FILE",
    "KOLOVIBE_SMTP_USER": "KOLOVIBE_SMTP_USER_FILE",
    "KOLOVIBE_SMTP_PASSWORD": "KOLOVIBE_SMTP_PASSWORD_FILE",  # pragma: allowlist secret
    "KOLOVIBE_MFA_ENCRYPTION_KEY": "KOLOVIBE_MFA_ENCRYPTION_KEY_FILE",
    "KOLOVIBE_IDENTITY_AUDIT_SIGNING_KEY": "KOLOVIBE_OUTBOUND_KEY_FILE",
}
CONFIG_FILES = {
    "KOLOVIBE_IDENTITY_AUDIT_PEERS": "KOLOVIBE_TRUSTED_PEERS_FILE",
    "KOLOVIBE_IDENTITY_APPROVALS": "KOLOVIBE_ACCOUNT_APPROVAL_FILE",
}


@contextmanager
def secret_environment(values):
    with tempfile.TemporaryDirectory(prefix="kolovibe-identity-secret-check-") as directory:
        environment = {}
        for name, target in {**SECRET_FILES, **CONFIG_FILES}.items():
            value = values.get(name, "")
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"Missing protected identity configuration: {name}")
            path = Path(directory) / target
            path.touch(mode=0o600)
            path.write_text(value)
            environment[target] = str(path)
        yield environment


def main():
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    with secret_environment(os.environ) as files:
        environment = {key: value for key, value in os.environ.items()
                       if key not in SECRET_FILES and key not in CONFIG_FILES}
        environment.update(files, KOLOVIBE_ENV="staging", DJANGO_DEBUG="0",
                           KOLOVIBE_SERVICE_NAME="identity", KOLOVIBE_STAGING_ACCOUNTS="1",
                           KOLOVIBE_STAGING_PRIVILEGED="1", PYTHONPATH=str(root / "services"))
        result = subprocess.run(
            [sys.executable, "-m", "staging_runtime.launch", "--check-settings"],
            env=environment, capture_output=True, text=True, timeout=30)
        if result.returncode:
            # Never print an exception chain that might contain provider credentials.
            raise RuntimeError("Protected identity configuration failed offline validation")
    print("Identity SMTP/TLS/MFA/audit configuration validated offline; no email or network calls")


if __name__ == "__main__":
    main()
