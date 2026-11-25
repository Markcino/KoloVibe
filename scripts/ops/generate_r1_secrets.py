"""Generate the R1 staging secret files (owner-only, outside the repository) and check them offline.

Nothing here contacts AWS. It writes one file per Swarm secret into a new 0700 directory, never overwrites, prints
file and secret NAMES only (never a value), then validates the set against the rules the staging runtime enforces:
secret lengths, exact JSON shapes, the Gateway peer set, distinct signing keys per audience, a valid Fernet key, and
that every receiver's callers file carries exactly the key the Gateway (or Moderation, Points, Identity) will sign with.

R2 comes from the repository's own `.env`: KOLOVIBE_R2_ACCESS_KEY_ID and KOLOVIBE_R2_SECRET_ACCESS_KEY are written as
files only when they have the shape Cloudflare issues; the account id and bucket are checked, never written.

Usage:  python3 scripts/ops/generate_r1_secrets.py [--out DIR] [--env .env]
        python3 scripts/ops/generate_r1_secrets.py --validate-only --out DIR
"""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services"), str(ROOT / "scripts/ops")]

from staging_runtime import capabilities as policy  # noqa: E402

BROKER_HOST, BROKER_PORT, BROKER_VHOST = "kolovibe-rabbitmq", 5671, "/kolovibe"
BROKER_ACCOUNTS = {"content": "kolovibe_content", "engagement": "kolovibe_engagement", "points": "kolovibe_points"}
# Least-privilege RabbitMQ grants per service: (configure, write, read) regular expressions over resource names in the vhost.
# Content owns its media queue. Points owns its queue and exchange. Engagement owns its queue and may only WRITE to the
# pre-provisioned Points exchange (it must not read, consume or declare it). Proven against a real broker by
# scripts/verify_event_pipeline_broker.py, which provisions accounts from this table.
BROKER_PERMISSIONS = {
    "content": (r"^kolovibe\.content\.media$",) * 3,
    "engagement": (r"^kolovibe\.engagement$", r"^(kolovibe\.engagement|kolovibe\.points)$", r"^kolovibe\.engagement$"),
    "points": (r"^kolovibe\.points$",) * 3,
}
RECEIVERS = ("identity", "content", "creators", "engagement", "points", "moderation")
ALL_CAPS = frozenset(policy.CAPABILITIES) - {"audit_read"}
APPROVAL_REFERENCES = ("identity", "smtp", "credentials", "transport", "mfa", "audit")


def origin(service):
    return f"https://{service}:8000"


def token():
    return secrets.token_urlsafe(48)


def build(env_values, *, audit_read=False):
    """{secret name: text} for every generated file, plus a list of notes about what was not generated."""
    from cryptography.fernet import Fernet

    notes, files = [], {}
    receivers = RECEIVERS + (("audit",) if audit_read else ())
    gateway_keys = {service: token() for service in receivers}
    moderation_keys = {"audit": token(), "content": token()}
    points_key, identity_key = token(), token()
    peers = sorted(policy.gateway_peers(ALL_CAPS | ({"audit_read"} if audit_read else set()), True))
    files["kolovibe_gateway_trusted_peers_r1_v1"] = json.dumps({s: origin(s) for s in peers}, indent=1)
    files["kolovibe_gateway_outbound_r1_v1"] = json.dumps(gateway_keys, indent=1)
    files["kolovibe_account_approval_r1_v1"] = json.dumps(
        {name: "R1-STAGING-2026-11-14-OWNER-DECISION" for name in APPROVAL_REFERENCES}, indent=1)
    files["identity_mfa_encryption"] = Fernet.generate_key().decode()
    files["identity_audit_signing"] = identity_key
    files["identity_audit_peers"] = json.dumps({"audit": origin("audit")})
    files["kolovibe_points_outbound_key_r1_v1"] = points_key
    files["kolovibe_points_audit_peers_r1_v1"] = json.dumps({"audit": origin("audit")})
    files["kolovibe_moderation_outbound_key_r1_v1"] = json.dumps(moderation_keys, indent=1)
    files["kolovibe_moderation_peers_r1_v1"] = json.dumps({"audit": origin("audit"), "content": origin("content")}, indent=1)
    for service in RECEIVERS:
        callers = {"gateway": gateway_keys[service]}
        if service == "content":
            callers["moderation"] = moderation_keys["content"]
        files[f"{service}_callers_2"] = json.dumps(callers, indent=1)
    files["audit_callers_2"] = json.dumps(
        {"identity": identity_key, "moderation": moderation_keys["audit"], "points": points_key} | ({"gateway": gateway_keys["audit"]} if audit_read else {}), indent=1)
    uri = "amqps://{user}:{password}@%s:%d/%s" % (BROKER_HOST, BROKER_PORT, BROKER_VHOST.replace("/", "%2F"))
    for service, user in BROKER_ACCOUNTS.items():
        files[f"kolovibe_{service}_rabbitmq_url_r1_v1"] = uri.format(user=user, password=token())
    access, secret = env_values.get("KOLOVIBE_R2_ACCESS_KEY_ID", ""), env_values.get("KOLOVIBE_R2_SECRET_ACCESS_KEY", "")
    if re.fullmatch(r"[0-9a-f]{32}", access) and re.fullmatch(r"[0-9a-f]{64}", secret):
        files["kolovibe_content_r2_access_key_r1_v1"] = access
        files["kolovibe_content_r2_secret_key_r1_v1"] = secret
    else:
        problems = []
        if not re.fullmatch(r"[0-9a-f]{32}", access):
            problems.append("KOLOVIBE_R2_ACCESS_KEY_ID " + ("is missing" if not access else "is not 32 hex characters"))
        if not re.fullmatch(r"[0-9a-f]{64}", secret):
            problems.append("KOLOVIBE_R2_SECRET_ACCESS_KEY " + ("is missing" if not secret else "is not 64 hex characters"))
        notes.append("R2 key files NOT written: " + "; ".join(problems))
    if not re.fullmatch(r"[0-9a-f]{32}", env_values.get("KOLOVIBE_R2_ACCOUNT_ID", "")):
        notes.append("KOLOVIBE_R2_ACCOUNT_ID is not a 32-character hex id (needed as a deployment input)")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", env_values.get("KOLOVIBE_R2_MEDIA_BUCKET", "")):
        notes.append("KOLOVIBE_R2_MEDIA_BUCKET is not a plain bucket name (needed as a deployment input)")
    return files, notes


def write_all(directory, files):
    directory = Path(directory).expanduser()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    for name, text in files.items():
        descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # never overwrite
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)  # no trailing newline: the value is exactly the file
    return directory


def read_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        text = line.strip()
        if text and not text.startswith("#") and "=" in text:
            key, value = text.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def validate(directory, *, audit_read=False):
    """Names and pass/fail only. Raises ValueError on the first problem."""
    from cryptography.fernet import Fernet

    directory = Path(directory).expanduser()
    if directory.stat().st_mode & 0o077:
        raise ValueError("The secret directory must be owner-only")

    def load(name):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError(f"{name}: missing or not an owner-only regular file")
        text = path.read_text()
        if text != text.strip() or not text:
            raise ValueError(f"{name}: empty, or has leading or trailing whitespace or a newline")
        return text

    def keymap(name, audiences):
        data = json.loads(load(name))
        if set(data) != set(audiences) or any(not isinstance(v, str) or len(v) < 32 for v in data.values()):
            raise ValueError(f"{name}: wrong audiences or a key under 32 characters")
        if len(set(data.values())) != len(data):
            raise ValueError(f"{name}: keys must be distinct")
        return data

    checked = []
    gateway = keymap("kolovibe_gateway_outbound_r1_v1", RECEIVERS + (("audit",) if audit_read else ()))
    peers = json.loads(load("kolovibe_gateway_trusted_peers_r1_v1"))
    if set(peers) != policy.gateway_peers(ALL_CAPS | ({"audit_read"} if audit_read else set()), True) or any(v != origin(k) for k, v in peers.items()):
        raise ValueError("kolovibe_gateway_trusted_peers_r1_v1: must be exactly the capability-required HTTPS origins")
    approvals = json.loads(load("kolovibe_account_approval_r1_v1"))
    if set(approvals) != set(APPROVAL_REFERENCES) or any(not v.strip() for v in approvals.values()):
        raise ValueError("kolovibe_account_approval_r1_v1: needs the six approval references")
    Fernet(load("identity_mfa_encryption").encode())
    identity_key = load("identity_audit_signing")
    points_key = load("kolovibe_points_outbound_key_r1_v1")
    moderation = keymap("kolovibe_moderation_outbound_key_r1_v1", ("audit", "content"))
    if min(len(identity_key), len(points_key)) < 32:
        raise ValueError("A signing key is under 32 characters")
    for name, expected in (("identity_audit_peers", {"audit"}), ("kolovibe_points_audit_peers_r1_v1", {"audit"}),
                           ("kolovibe_moderation_peers_r1_v1", {"audit", "content"})):
        data = json.loads(load(name))
        if set(data) != expected or any(v != origin(k) for k, v in data.items()):
            raise ValueError(f"{name}: must name exactly {sorted(expected)} as HTTPS origins")
    for service in (name for name in RECEIVERS if name != "audit"):
        callers = json.loads(load(f"{service}_callers_2"))
        want = {"gateway": gateway[service]}
        if service == "content":
            want["moderation"] = moderation["content"]
        if callers != want:
            raise ValueError(f"{service}_callers_2: must carry exactly the key its caller signs with")
    audit = json.loads(load("audit_callers_2"))
    if audit != ({"identity": identity_key, "moderation": moderation["audit"], "points": points_key} | ({"gateway": gateway["audit"]} if audit_read else {})):
        raise ValueError("audit_callers_2: must carry the Identity, Moderation, Points and Gateway audit keys")
    if len(set(audit.values())) != (4 if audit_read else 3):
        raise ValueError("audit_callers_2: keys must be distinct")
    every = [*gateway.values(), *moderation.values(), identity_key, points_key]
    if len(set(every)) != len(every):
        raise ValueError("A signing key is reused between audiences")
    for service in BROKER_ACCOUNTS:
        value = load(f"kolovibe_{service}_rabbitmq_url_r1_v1")
        if not re.fullmatch(r"amqps://kolovibe_%s:[A-Za-z0-9_-]{32,}@%s:%d/%%2Fkolovibe" % (service, BROKER_HOST, BROKER_PORT), value):
            raise ValueError(f"kolovibe_{service}_rabbitmq_url_r1_v1: wrong shape")
    r2 = [name for name in ("kolovibe_content_r2_access_key_r1_v1", "kolovibe_content_r2_secret_key_r1_v1")
          if (directory / name).exists()]
    if r2 and sorted(r2) != ["kolovibe_content_r2_access_key_r1_v1", "kolovibe_content_r2_secret_key_r1_v1"]:
        raise ValueError("R2 needs both the access key id and the secret key")
    checked = sorted(p.name for p in directory.iterdir() if p.is_file())
    return checked


def scripts_text(directory, names):
    manager = "swarm-manager"
    create = ["#!/bin/bash", "# Creates each Swarm secret from its file, once. Refuses to replace an existing secret. Run only after approval.",
              "set -euo pipefail", f'cd "{directory}"', ""]
    for name in names:
        create.append(f'if ssh -o BatchMode=yes {manager} "sudo -n docker secret inspect {name} >/dev/null 2>&1"; then echo "EXISTS (skipped): {name}"; '
                      f'else ssh -o BatchMode=yes {manager} "sudo -n docker secret create {name} -" < "{name}" >/dev/null && echo "created: {name}"; fi')
    users = " ".join(f"{s}:{u}" for s, u in BROKER_ACCOUNTS.items())
    # Each account gets only its own resources (BROKER_PERMISSIONS), never a wildcard. The patterns sit in single quotes, so
    # they stay literal; the remote command receives them by variable expansion, which is not parsed again.
    grants = ["  case \"$svc\" in"]
    for service, (configure, write, read) in BROKER_PERMISSIONS.items():
        for value in (configure, write, read):
            if "'" in value:
                raise ValueError("A broker permission pattern cannot contain a single quote")
        grants.append(f"    {service}) conf='{configure}'; wr='{write}'; rd='{read}';;")
    grants += ["    *) echo \"no broker permissions defined for $svc\" >&2; exit 1;;", "  esac"]
    broker = ["#!/bin/bash", "# Creates the three per-service RabbitMQ accounts in the existing vhost, with the passwords already inside the",
              "# generated URI files (read here, never printed). Each account is limited to its own queues and exchanges.",
              "# Run only after approval.", "set -euo pipefail", f'cd "{directory}"',
              f'WORKER=swarm-worker; VHOST="{BROKER_VHOST}"', f'for pair in {users}; do',
              '  svc="${pair%%:*}"; user="${pair##*:}"', *grants,
              '  pw="$(python3 -c \'import sys,urllib.parse as u; print(u.urlsplit(open(sys.argv[1]).read()).password)\' "kolovibe_${svc}_rabbitmq_url_r1_v1")"',
              '  ssh -o BatchMode=yes $WORKER "CID=\\$(sudo -n docker ps -q --filter label=com.docker.swarm.service.name=kolovibe-rabbitmq | head -1); '
              'sudo -n docker exec \\$CID rabbitmqctl -q add_user $user \'$pw\' && sudo -n docker exec \\$CID rabbitmqctl -q set_permissions -p $VHOST $user \'$conf\' \'$wr\' \'$rd\'" >/dev/null',
              '  echo "account ready: $user"', "done"]
    return "\n".join(create) + "\n", "\n".join(broker) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="~/kolovibe-r1-secrets")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--audit-read", action="store_true", help="Prepare credentials for a separately approved audit_read profile; does not activate it")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    directory = Path(args.out).expanduser()
    if not args.validate_only:
        if directory.exists() and any(directory.iterdir()):
            raise SystemExit("Refusing to write into a non-empty directory: " + str(directory))
        if str(directory.resolve()).startswith(str(ROOT)):
            raise SystemExit("Choose a directory outside the repository")
        files, notes = build(read_env(args.env), audit_read=args.audit_read)
        write_all(directory, files)
        create, broker = scripts_text(directory, sorted(files))
        for name, text in (("create-secrets.sh", create), ("broker-setup.sh", broker)):
            write_all(directory.parent / (directory.name + "-scripts"), {name: text})
            (directory.parent / (directory.name + "-scripts") / name).chmod(0o700)
        for note in notes:
            print("NOTE:", note)
    names = validate(directory, audit_read=args.audit_read)
    print(f"PASS: {len(names)} secret files in {directory} (owner-only; values not shown):")
    for name in names:
        print("  ", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
