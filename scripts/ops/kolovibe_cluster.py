#!/usr/bin/env python3
"""Deploy or move KoloVibe services to an approved image and collect credential-free live evidence.

Run worker-preflight on VM2; copy its JSON to VM1 before deploy/update. `deploy` only creates
missing services. `update-plan`/`update` move named, already-deployed services to an explicit
digest one at a time (dry-run unless confirmed), and `rollback` restores the previous spec.
No image is ever defaulted. PostgreSQL, firewall, DNS and Nginx are never modified, and the
Gateway changes only when it is explicitly named.
"""
import argparse
import base64
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
import getpass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request
from urllib.error import HTTPError

SERVICES = ('gateway', 'content', 'creators', 'identity', 'engagement', 'points', 'moderation', 'audit')
REPOSITORY = 'ghcr.io/markcino/kolovibe/services'
# The 1 November image the running staging services were created from. It is only the
# historical baseline: it is never a deployment target and never a silent default.
BASELINE_IMAGE = REPOSITORY + '@sha256:8d6a16e450e6a7825c7d501069cd54fa3a75776afc2819e5664499bcef85ea14'
# Published Git commit identifier, not an authentication credential.
BASELINE_REVISION = 'be03dbcced01f1a4f71c643dbc179da2810ffa61'  # pragma: allowlist secret
IMAGE, REVISION = BASELINE_IMAGE, BASELINE_REVISION  # legacy names for the baseline only
IMAGE_RE = re.compile(re.escape(REPOSITORY) + r'@sha256:[0-9a-f]{64}')
REVISION_RE = re.compile(r'[0-9a-f]{40}')
REF_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{3,63}')
# Leaf-most services first so audit ingest is ready before its producers; the public
# Gateway is always last and is rolled back first.
UPDATE_ORDER = ('audit', 'identity', 'creators', 'content', 'engagement', 'points', 'moderation', 'gateway')
# Swarm rolling-update guards recorded in infra/swarm/staging.yml.
UPDATE_CONFIG = {'Parallelism': 1, 'Delay': 0, 'FailureAction': 'rollback', 'Monitor': 30_000_000_000,
                 'MaxFailureRatio': 0, 'Order': 'stop-first'}
ROLLBACK_CONFIG = {'Parallelism': 1, 'Delay': 0, 'FailureAction': 'pause', 'Monitor': 30_000_000_000,
                   'MaxFailureRatio': 0, 'Order': 'stop-first'}
ROLLING_KEYS = ('UpdateConfig', 'RollbackConfig')
POLICY = Path('/etc/docker/policies/authz.rego')
BASE = '''package docker.authz
default allow = false
allow { input.Method == "GET" }
allow { input.Method == "HEAD" }
'''
LABEL = 'kolovibe.cluster-launcher'
MIB = 1024 * 1024
# Swarm object names/filename suffixes only; the secret values are never loaded here.
COMMON = {'django_key': '_django', 'db_password': '_db', 'tls_cert': '_tls_cert',  # pragma: allowlist secret
          'tls_key': '_tls_key', 'caller_keys': '_callers', 'probe_token': '_probe'}
EXTRA = {'identity': {'smtp_user': 'identity_smtp_user', 'smtp_password': 'identity_smtp_password',  # pragma: allowlist secret
                    'mfa_encryption_key': 'identity_mfa_encryption',
                    'audit_signing_key': 'identity_audit_signing', 'audit_peers': 'identity_audit_peers',
                    'account_approvals': 'identity_approvals'}}


def fail(message):
    raise RuntimeError('BLOCKED: ' + message)


def run(args, *, data=None, timeout=30):
    result = subprocess.run(args, input=data, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        fail(args[0] + ' failed; command output suppressed')
    return result.stdout


def root(host):
    if os.geteuid() != 0 or socket.gethostname() != host:
        fail('Run with sudo on ' + host)


class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')


def docker(method, path, body=None, auth=None):
    connection = DockerConnection('localhost', timeout=45)
    headers = {'Content-Type': 'application/json'}
    if auth:
        headers['X-Registry-Auth'] = auth
    try:
        connection.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        response = connection.getresponse()
        raw = response.read()
        if response.status >= 300:
            fail('Docker ' + method + ' returned HTTP ' + str(response.status))
        return json.loads(raw) if raw else {}
    finally:
        connection.close()


def policy_baseline():
    if POLICY.is_symlink() or not POLICY.is_file() or POLICY.stat().st_uid != 0:
        fail('Expected root-owned OPA policy is absent')
    original = POLICY.read_bytes()
    cleaned = '\n'.join(line.split('#', 1)[0] for line in original.decode().splitlines())
    if re.sub(r'\s+', '', cleaned) != re.sub(r'\s+', '', BASE):
        fail('OPA policy differs from GET/HEAD-only baseline')
    return original


def atomic_policy(raw):
    fd, name = tempfile.mkstemp(prefix='.kv-cluster-', dir=POLICY.parent)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, POLICY)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def allow_once(api, path, body):
    """Exact method/path/body, independent timer, unconditional policy restoration."""
    original = policy_baseline()
    suffix = secrets.token_hex(6)
    backup = POLICY.parent / ('.kv-cluster-backup-' + suffix)
    watchdog = POLICY.parent / ('.kv-cluster-restore-' + suffix)
    unit = 'kv-cluster-restore-' + suffix
    armed = False
    changed = False
    old_signals = {}
    try:
        with backup.open('xb') as handle:
            os.chmod(backup, 0o600)
            handle.write(original)
        script = ('#!/bin/sh\nset -eu\nT=$(mktemp /etc/docker/policies/.kv-cluster-wd.XXXXXX)\n'
                  'trap \'rm -f "$T"\' EXIT\ncp ' + shlex.quote(str(backup)) + ' "$T"\n'
                  'chmod 644 "$T"\nmv -f "$T" ' + shlex.quote(str(POLICY)) + '\n')
        with watchdog.open('x') as handle:
            os.chmod(watchdog, 0o700)
            handle.write(script)
        run(['systemd-run', '--quiet', '--on-active=3min', '--unit=' + unit, str(watchdog)])
        armed = True
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            old_signals[number] = signal.signal(number, lambda n, f: sys.exit(128 + n))
        rule = ('\nallow {\n input.Method == "POST"\n input.PathPlain == ' + json.dumps(path)
                + '\n input.Body == ' + json.dumps(body, separators=(',', ':')) + '\n}\n')
        atomic_policy(original + rule.encode())
        changed = True
        yield
    finally:
        if changed:
            atomic_policy(original)
        # Keep recovery files/timer if restoration itself fails.
        if armed and POLICY.read_bytes() == original:
            run(['systemctl', 'stop', unit + '.timer'])
            backup.unlink(missing_ok=True)
            watchdog.unlink(missing_ok=True)
        for number, previous in old_signals.items():
            signal.signal(number, previous)
        if changed:
            # A 403 on this deliberately unauthorized write is mandatory evidence.
            connection = DockerConnection('localhost', timeout=10)
            try:
                connection.request('POST', '/v' + api + '/secrets/create', '{}',
                                   {'Content-Type': 'application/json'})
                response = connection.getresponse()
                response.read()
                if response.status != 403:
                    fail('OPA write-denial verification failed')
            finally:
                connection.close()
            print('PASS: GET/HEAD-only OPA restored; unrelated secret write denied (403)', file=sys.stderr)


def safe_spec(spec):
    container = spec['TaskTemplate']['ContainerSpec']
    if (container.get('PullOptions') or {}).get('RegistryAuth'):
        fail('Unexpected inspect credential; refusing to serialize service')
    # Only file-backed credentials may be serialized into OPA policy bodies.
    for item in container.get('Env', []):
        key = item.split('=', 1)[0]
        if re.search(r'PASSWORD|TOKEN|SECRET|CREDENTIAL|PRIVATE_KEY', key) and not key.endswith('_FILE'):
            fail('Inline credential-like environment variable requires review')


def env_dict(container):
    return dict(item.split('=', 1) for item in container.get('Env', []) if '=' in item)


def canonical(value):
    """Ignore API-inserted empty defaults; retain every substantive spec field."""
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if v not in (None, '', 0, False, [], {})}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    return value


def resolve_release(image=None, revision=None, release_dir=None):
    """Return the one approved (image, revision) target, or stop.

    The target is never defaulted. It comes from the operator naming a digest, or from the
    `published-image-<sha>` artifact written by the CI publish job, which only runs after
    the image scan, the SQLite-free checks and the eight-service smoke matrix pass. A
    digest that was not published by that job cannot be cross-checked, so --release-dir
    is the preferred input and --image/--revision alone are only a shape check.
    """
    if release_dir:
        base = Path(release_dir)
        def text(name):
            path = base / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
                fail('Release evidence file is missing or unsafe: ' + name)
            return path.read_text().strip()
        published, rev, tag = text('published-digest.txt'), text('revision.txt'), text('published-tag.txt')
        if image not in (None, published) or revision not in (None, rev):
            fail('--image/--revision disagree with the published release evidence')
        if tag.split(':', 1)[0] != REPOSITORY or not tag.split(':', 1)[1:] \
                or not tag.split(':', 1)[1].startswith(rev + '-'):
            fail('Published tag does not belong to the recorded revision')
        try:
            names = json.loads(text('services.json'))
            components = json.loads(text('image-sbom.json'))['components']
        except (ValueError, KeyError, TypeError):
            fail('Release evidence is not valid JSON')
        if sorted(names) != sorted(SERVICES):
            fail('Release evidence lists a different service set')
        if not components or any('sqlite' in str(c.get('name', '')).lower() for c in components):
            fail('Release SBOM is empty or lists SQLite; the scan gate was not satisfied')
        image, revision = published, rev
    if not image or not IMAGE_RE.fullmatch(image):
        fail('Supply an immutable ' + REPOSITORY + '@sha256:<digest> via --release-dir or --image')
    if not revision or not REVISION_RE.fullmatch(revision):
        fail('Supply the 40-hex release commit via --release-dir or --revision')
    if image == BASELINE_IMAGE:
        fail('The 1 November baseline image is not an approved release target')
    return image, revision


def pinned(spec, image, revision):
    spec = copy.deepcopy(spec)
    spec['TaskTemplate']['ContainerSpec']['Image'] = image
    spec.setdefault('Labels', {})['kolovibe.source-revision'] = revision
    return spec


def release_neutral(spec):
    """A spec with the release pin and rolling-update guards removed, for drift checks."""
    spec = pinned(spec, '', '')
    for key in ROLLING_KEYS:
        spec.pop(key, None)
    return canonical(spec)


def spec_digest(spec):
    return hashlib.sha256(json.dumps(canonical(spec), sort_keys=True).encode()).hexdigest()


def live_image(spec):
    return ((spec.get('TaskTemplate') or {}).get('ContainerSpec') or {}).get('Image', '')


def base_gateway(api, image=BASELINE_IMAGE):
    gateway = docker('GET', '/v' + api + '/services/kvtest-gateway')
    spec = gateway['Spec']
    safe_spec(spec)
    c = spec['TaskTemplate']['ContainerSpec']
    env = env_dict(c)
    required = {'KOLOVIBE_ENV': 'staging', 'KOLOVIBE_SERVICE_NAME': 'gateway',
                'KOLOVIBE_DB_HOST': 'vm-swarm-worker', 'KOLOVIBE_DB_NAME': 'kolovibe_staging',
                'KOLOVIBE_DB_USER': 'kv_gateway_run', 'KOLOVIBE_STAGING_ACCOUNTS': '0',
                'KOLOVIBE_STAGING_PRIVILEGED': '0'}
    # The Gateway is either still on the working baseline or already on a reviewed target.
    if any(env.get(k) != v for k, v in required.items()) or c.get('Image') not in (BASELINE_IMAGE, image):
        fail('Gateway differs from the working pinned baseline')
    if not c.get('ReadOnly') or c.get('User') != '10001:10001':
        fail('Gateway runtime hardening differs')
    if (spec.get('EndpointSpec') or {}).get('Ports') or spec['Mode'] != {'Replicated': {'Replicas': 1}}:
        fail('Gateway must be private and single replica')
    if 'node.hostname == vm-swarm-worker' not in spec['TaskTemplate']['Placement']['Constraints']:
        fail('Gateway must remain pinned to VM2')
    nets = {}
    for attachment in spec['TaskTemplate'].get('Networks', []):
        net = docker('GET', '/v' + api + '/networks/' + attachment['Target'])
        nets[net['Name']] = net
        if net.get('Driver') != 'overlay' or 'encrypted' not in (net.get('Options') or {}):
            fail('Gateway overlay encryption differs')
    if set(nets) != {'kolovibe_services', 'kolovibe_data', 'kolovibe_db_host_access'}:
        fail('Gateway networks differ from working baseline')
    if not nets['kolovibe_services']['Internal'] or not nets['kolovibe_data']['Internal']:
        fail('Existing private networks must remain internal')
    return gateway


def api_spec(gateway, service, all_secrets, image, revision):
    spec = copy.deepcopy(gateway['Spec'])
    spec['Name'] = 'kvtest-' + service
    spec['Labels'] = {LABEL: '1', 'kolovibe.source-revision': revision}
    spec['TaskTemplate']['ContainerSpec']['Image'] = image
    spec.pop('UpdateConfig', None)
    spec.pop('RollbackConfig', None)
    spec['EndpointSpec'] = {'Mode': 'vip'}
    task = spec['TaskTemplate']
    c = task['ContainerSpec']
    c.pop('Hostname', None)
    c.pop('Labels', None)
    env = env_dict(c)
    # Retain the proven DB host and hosts entry. Replace service-specific identity.
    env.update(KOLOVIBE_SERVICE_NAME=service, KOLOVIBE_ALLOWED_HOSTS=service,
               KOLOVIBE_DB_USER='kv_' + service + '_run')
    for key in ('KOLOVIBE_TRUSTED_PEERS_FILE', 'KOLOVIBE_OUTBOUND_KEY_FILE'):
        env.pop(key, None)
    if service == 'identity':
        env.update(KOLOVIBE_SMTP_USER_FILE='/run/secrets/smtp_user',
                   KOLOVIBE_SMTP_PASSWORD_FILE='/run/secrets/smtp_password',
                   KOLOVIBE_MFA_ENCRYPTION_KEY_FILE='/run/secrets/mfa_encryption_key',
                   KOLOVIBE_OUTBOUND_KEY_FILE='/run/secrets/audit_signing_key',
                   KOLOVIBE_TRUSTED_PEERS_FILE='/run/secrets/audit_peers',
                   KOLOVIBE_ACCOUNT_APPROVAL_FILE='/run/secrets/account_approvals')
    c['Env'] = [key + '=' + value for key, value in sorted(env.items())]
    selected = {target: service + suffix for target, suffix in COMMON.items()}
    selected.update(EXTRA.get(service, {}))
    selected.update(internal_ca='internal_ca', db_ca='db_ca')
    c['Secrets'] = []
    for target, name in selected.items():
        if name not in all_secrets:
            fail('Missing existing Swarm secret: ' + name)
        c['Secrets'].append({'SecretID': all_secrets[name], 'SecretName': name,
                            'File': {'Name': target, 'UID': '10001', 'GID': '10001', 'Mode': 256}})
    for attachment in task['Networks']:
        attachment.pop('Aliases', None)
        attachment.pop('Addresses', None)
        # Names, never fixed task IPs, locate API services.
        attachment['Aliases'] = [service]
    # New services use readiness healthchecks. Existing Gateway stays unchanged.
    c['Healthcheck'] = {'Test': ['CMD', 'python', '-m', 'staging_runtime.probe'],
                        'Interval': 30_000_000_000, 'Timeout': 10_000_000_000,
                        'Retries': 3, 'StartPeriod': 60_000_000_000}
    task['RestartPolicy'] = {'Condition': 'on-failure', 'Delay': 5_000_000_000, 'MaxAttempts': 3}
    task['Resources'] = {'Limits': {'MemoryBytes': 256*MIB, 'NanoCPUs': 1_000_000_000},
                         'Reservations': {'MemoryBytes': 128*MIB}}
    safe_spec(spec)
    return spec


def broker_candidate(services, api):
    candidates = [s for s in services if re.search(r'(?:_|-)rabbitmq$', s['Spec']['Name'])]
    if len(candidates) != 1:
        return None, 'A single existing RabbitMQ candidate is required; no broker image was guessed'
    broker = candidates[0]
    spec = broker['Spec']
    safe_spec(spec)
    c = spec['TaskTemplate']['ContainerSpec']
    if not re.fullmatch(r'dhi.io/rabbitmq@sha256:[a-f0-9]{64}', c.get('Image', '')):
        return None, 'RabbitMQ candidate needs an immutable DHI digest'
    constraints = spec['TaskTemplate'].get('Placement', {}).get('Constraints', [])
    if 'node.labels.kolovibe.workloads == true' not in constraints:
        return None, 'RabbitMQ lacks the worker workload constraint'
    if (spec.get('EndpointSpec') or {}).get('Ports'):
        return None, 'RabbitMQ must not publish ports'
    required = {'kolovibe_rmq_ca', 'kolovibe_rmq_cert', 'kolovibe_rmq_key', 'kolovibe_rmq_definitions'}
    if {s['SecretName'] for s in c.get('Secrets', [])} != required:
        return None, 'RabbitMQ secret set differs from candidate'
    nets = spec['TaskTemplate'].get('Networks', [])
    if len(nets) != 1:
        return None, 'RabbitMQ must use only the messaging overlay'
    net = docker('GET', '/v' + api + '/networks/' + nets[0]['Target'])
    if net.get('Name') != 'kolovibe_messaging' or not net.get('Internal') or 'encrypted' not in (net.get('Options') or {}):
        return None, 'RabbitMQ messaging isolation differs'
    if not c.get('Configs') or not any(m.get('Type') == 'volume' and m.get('Target') == '/var/lib/rabbitmq' for m in c.get('Mounts', [])):
        return None, 'RabbitMQ config/persistent volume is absent'
    replicas = spec.get('Mode', {}).get('Replicated', {}).get('Replicas')
    limit = spec['TaskTemplate'].get('Resources', {}).get('Limits', {}).get('MemoryBytes', 0)
    if replicas not in (0, 1) or limit < 256*MIB:
        return None, 'RabbitMQ replica count or memory limit needs review'
    return broker, None


def load_evidence(path):
    evidence = json.loads(Path(path).read_text())
    if (evidence.get('kind') != 'KVB-CLUSTER-WORKER-V1' or evidence.get('host') != 'vm-swarm-worker'
            or not 0 <= time.time() - evidence.get('time', 0) <= 300
            or evidence.get('guard') is not True or evidence.get('gateway_live') is not True):
        fail('Fresh VM2 preflight with guard and Gateway TLS checks is required')
    return evidence


def manager_checks():
    """Read-only preconditions shared by every manager-side mode; returns the API version."""
    root('vm-swarm-manager')
    policy_baseline()
    version = docker('GET', '/version')['ApiVersion']
    if not re.fullmatch(r'\d+\.\d+', version):
        fail('Invalid Docker API version')
    info = docker('GET', '/v' + version + '/info')
    if not info['Swarm'].get('ControlAvailable') or info.get('Plugins', {}).get('Authorization') != ['openpolicyagent/opa-docker-authz-v2:0.9']:
        fail('Expected Swarm manager and OPA plugin are required')
    plugin = run(['docker', 'plugin', 'inspect', 'openpolicyagent/opa-docker-authz-v2:0.9',
                  '--format', '{{.Enabled}} {{json .Settings.Args}}']).strip()
    if plugin != 'true ["-policy-file","/opa/policies/authz.rego","-quiet"]':
        fail('OPA must be enabled with quiet logging before registry authentication')
    return version


def plan(evidence, image, revision):
    version = manager_checks()
    gateway = base_gateway(version, image)
    entries = docker('GET', '/v' + version + '/services')
    all_secrets = {s['Spec']['Name']: s['ID'] for s in docker('GET', '/v' + version + '/secrets')}
    if len(all_secrets) != 62:
        fail('Expected 62 existing Swarm secrets')
    existing = {s['Spec']['Name']: s for s in entries}
    new = []
    for service in SERVICES[1:]:
        name = 'kvtest-' + service
        actual = existing.get(name)
        if actual:
            # An existing service keeps its own release pin; moving it is `update`'s job.
            # Refuse to overwrite or adopt a service configured differently in any other way.
            pin = live_image(actual['Spec'])
            rev = (actual['Spec'].get('Labels') or {}).get('kolovibe.source-revision', '')
            if not IMAGE_RE.fullmatch(pin):
                fail('Existing service differs; inspect without overwriting: ' + name)
            expected = api_spec(gateway, service, all_secrets, pin, rev)
            if release_neutral(actual['Spec']) != release_neutral(expected):
                fail('Existing service differs; inspect without overwriting: ' + name)
        else:
            new.append(api_spec(gateway, service, all_secrets, image, revision))
    broker, blocked = broker_candidate(entries, version)
    broker_memory = 0
    if broker and broker['Spec']['Mode']['Replicated']['Replicas'] == 0:
        broker_memory = broker['Spec']['TaskTemplate']['Resources']['Limits']['MemoryBytes']
    need = len(new)*256*MIB + broker_memory + 384*MIB
    if evidence.get('available_memory_bytes', 0) < need:
        fail('VM2 capacity: need at least ' + str(need//MIB) + ' MiB available for planned limits plus headroom; observed '
             + str(evidence.get('available_memory_bytes', 0)//MIB) + ' MiB')
    worker = [n for n in docker('GET', '/v' + version + '/nodes') if n['Description']['Hostname'] == 'vm-swarm-worker']
    if len(worker) != 1 or worker[0]['Status']['State'] != 'ready' or worker[0]['Spec']['Availability'] != 'active':
        fail('VM2 must be Ready/Active')
    if broker:
        for constraint in broker['Spec']['TaskTemplate']['Placement']['Constraints']:
            if constraint == 'node.hostname == vm-swarm-worker':
                continue
            match = re.fullmatch(r'node.labels.([a-z.]+) == ([a-z0-9]+)', constraint)
            if not match or worker[0]['Spec'].get('Labels', {}).get(match[1]) != match[2]:
                broker, blocked = None, 'RabbitMQ placement labels are not satisfied on VM2'
                break
    return version, gateway, new, broker, blocked


def wait_running(api, sid):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        query = urlencode({'filters': json.dumps({'service': [sid], 'desired-state': ['running']})})
        tasks = docker('GET', '/v' + api + '/tasks?' + query)
        if len(tasks) == 1 and tasks[0]['Status']['State'] == 'running':
            return
        if any(t['Status']['State'] in ('failed', 'rejected') for t in tasks):
            fail('Task rejected/failed; inspect service ps before retrying')
        time.sleep(2)
    fail('Task did not reach Running within 120 seconds')


def registry_auth(username):
    if not username or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', username) or not sys.stdin.isatty():
        fail('Use ssh -t and --registry-user for the hidden GHCR read:packages token prompt')
    token = getpass.getpass('GHCR read:packages token (hidden): ')
    if len(token) < 20 or any(c.isspace() for c in token):
        fail('Invalid registry token')
    auth = base64.urlsafe_b64encode(json.dumps({'username': username, 'password': token,
                                              'serveraddress': 'ghcr.io'}).encode()).decode()
    del token
    return auth


def deploy(path, username, image, revision, dry_run=False):
    evidence = load_evidence(path)
    api, gateway, new, broker, blocked = plan(evidence, image, revision)
    print('PLAN: create ' + ', '.join(s['Name'] for s in new) + ' from ' + image
          + '; preserve kvtest-gateway unchanged; existing services keep their pin (use update-plan)', file=sys.stderr)
    if blocked:
        print('PENDING RabbitMQ: ' + blocked, file=sys.stderr)
    if dry_run:
        return
    auth = registry_auth(username) if new else None
    load_evidence(path)  # Recheck freshness after the interactive credential prompt.
    for spec in new:
        path_api = '/v' + api + '/services/create'
        with allow_once(api, path_api, spec):
            sid = docker('POST', path_api, spec, auth)['ID']
        wait_running(api, sid)
        print('RUNNING: ' + spec['Name'] + '; live verification still required', file=sys.stderr)
    if broker and broker['Spec']['Mode']['Replicated']['Replicas'] == 0:
        updated = copy.deepcopy(broker['Spec'])
        updated['Mode']['Replicated']['Replicas'] = 1
        constraints = updated['TaskTemplate']['Placement']['Constraints']
        if 'node.hostname == vm-swarm-worker' not in constraints:
            constraints.append('node.hostname == vm-swarm-worker')
        path_api = '/v' + api + '/services/' + broker['ID'] + '/update'
        query = '?version=' + str(broker['Version']['Index']) + '&registryAuthFrom=spec'
        with allow_once(api, path_api, updated):
            docker('POST', path_api + query, updated)
        wait_running(api, broker['ID'])
        print('RUNNING: ' + updated['Name'] + '; broker verification still required', file=sys.stderr)
    if docker('GET', '/v' + api + '/services/kvtest-gateway')['Spec'] != gateway['Spec']:
        fail('Gateway changed concurrently; investigate')
    if blocked:
        fail('APIs submitted; RabbitMQ remains pending: ' + blocked)


def ordered(services, reverse=False):
    """Validate an explicit service list and return it in the safe rollout order."""
    if not services:
        fail('Name the services explicitly with --services; nothing is selected by default')
    unknown = sorted(set(services) - set(UPDATE_ORDER))
    if unknown or len(set(services)) != len(services):
        fail('--services must be a unique subset of: ' + ', '.join(UPDATE_ORDER))
    order = tuple(reversed(UPDATE_ORDER)) if reverse else UPDATE_ORDER
    return [s for s in order if s in services]


def update_plan(evidence, image, revision, services, restore_ref=None):
    """Read-only plan to move named, already-deployed services to the approved image.

    Every entry records what a rollback needs *before* anything is changed. The spec for
    each service is the live spec with only the release pin and the rolling-update guards
    replaced; nothing else about the running service is altered.
    """
    names = ordered(services)
    api = manager_checks()
    base_gateway(api, image)
    if len(docker('GET', '/v' + api + '/secrets')) != 62:
        fail('Expected 62 existing Swarm secrets')
    existing = {s['Spec']['Name']: s for s in docker('GET', '/v' + api + '/services')}
    entries = []
    for service in names:
        name = 'kvtest-' + service
        live = existing.get(name)
        if not live:
            fail(name + ' is not deployed; update never creates services (use deploy)')
        spec = live['Spec']
        safe_spec(spec)
        current = live_image(spec)
        if not IMAGE_RE.fullmatch(current):
            fail(name + ' is not pinned to an immutable GHCR digest; inspect before updating')
        if spec.get('Mode') != {'Replicated': {'Replicas': 1}}:
            fail(name + ' must be a single replica service before an image update')
        if (spec.get('EndpointSpec') or {}).get('Ports'):
            fail(name + ' publishes ports; refusing to update')
        health = ((spec['TaskTemplate']['ContainerSpec'].get('Healthcheck') or {}).get('Test') or ['NONE'])[0]
        revision_now = (spec.get('Labels') or {}).get('kolovibe.source-revision', '')
        entries.append({
            'service': service, 'service_id': live['ID'], 'version_index': live['Version']['Index'],
            'current_image': current, 'current_revision': revision_now,
            'target_image': image, 'target_revision': revision,
            'action': 'unchanged' if current == image else 'update',
            'health_gated': health not in ('NONE', ''), 'spec_sha256': spec_digest(spec),
            'update_spec': update_spec(spec, image, revision),
            'previous_spec_available': bool(live.get('PreviousSpec')),
            'rollback': {
                'image_rollback': 'python3 kolovibe_cluster.py rollback --services ' + service
                                  + ' --confirm-rollback ' + service,
                'repin': 'python3 kolovibe_cluster.py update --services ' + service + ' --release-dir <prior approved release>',
                'schema': 'Forward-only: image rollback never reverses migrations. Restore from the '
                          'owner-approved restore point and export evidence tables first.'}})
    return {'api': api, 'image': image, 'revision': revision, 'restore_point_ref': restore_ref,
            'entries': entries, 'evidence_time': evidence.get('time')}


def update_spec(spec, image, revision):
    new = pinned(spec, image, revision)
    new['UpdateConfig'] = dict(UPDATE_CONFIG)
    new['RollbackConfig'] = dict(ROLLBACK_CONFIG)
    if release_neutral(new) != release_neutral(spec):
        fail('Update would change more than the release pin')
    safe_spec(new)
    return new


def public_plan(report):
    """The plan as printed and recorded: no full specs, which can name secret objects."""
    shown = [{k: v for k, v in entry.items() if k != 'update_spec'} for entry in report['entries']]
    return dict(report, entries=shown)


def write_private(path, document):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(json.dumps(document, indent=2) + '\n')


def wait_update(api, sid, previous_started, expected_image, *, rollback=False, timeout=300):
    """Block until Swarm reports this update finished; any rollback or pause is a failure."""
    deadline = time.monotonic() + timeout
    good = 'rollback_completed' if rollback else 'completed'
    while time.monotonic() < deadline:
        service = docker('GET', '/v' + api + '/services/' + sid)
        status = service.get('UpdateStatus') or {}
        if status.get('StartedAt') != previous_started:
            state = status.get('State')
            if state == good:
                if not rollback and live_image(service['Spec']) != expected_image:
                    fail('Service finished updating on an unexpected image')
                return
            bad = ('paused', 'rollback_paused') if rollback else ('paused', 'rollback_started', 'rollback_completed',
                                                                   'rollback_paused')
            if state in bad:
                fail('Swarm reported ' + state + '; the service is not on the target image')
        time.sleep(2)
    fail('Update did not finish within ' + str(timeout) + ' seconds')


def update(path, username, image, revision, services, restore_ref, confirm_image, rollback_file, accept_ungated):
    """Dry-run unless --confirm-image repeats the approved digest exactly."""
    evidence = load_evidence(path)
    report = update_plan(evidence, image, revision, services, restore_ref)
    shown = public_plan(report)
    print(json.dumps(shown, indent=2), file=sys.stderr)
    todo = [e for e in report['entries'] if e['action'] == 'update']
    if confirm_image is None:
        print('DRY RUN: add --confirm-image ' + image + ' to apply; nothing was changed', file=sys.stderr)
        return
    if confirm_image != image:
        fail('--confirm-image must repeat the approved release digest exactly')
    if not restore_ref or not REF_RE.fullmatch(restore_ref):
        fail('--restore-point-ref must name the owner-approved pre-migration restore point')
    ungated = [e['service'] for e in todo if not e['health_gated']]
    if ungated and not accept_ungated:
        fail('No readiness healthcheck, so Swarm cannot detect a bad image for: ' + ', '.join(ungated)
             + '; add --accept-ungated only with verify-worker/verify-edge run immediately after')
    if not todo:
        print('NOTHING TO DO: every named service is already on the target image', file=sys.stderr)
        return
    # The rollback record is written first and exclusively, so it can never be overwritten.
    write_private(rollback_file, dict(shown, accept_ungated=bool(ungated and accept_ungated),
                                      note='Restore point attested by the operator; restore not verified by this tool.'))
    auth = registry_auth(username)
    load_evidence(path)  # Recheck freshness after the interactive credential prompt.
    api = report['api']
    remaining = [e['service'] for e in todo]
    gateway_before = None if 'gateway' in services else docker('GET', '/v' + api + '/services/kvtest-gateway')['Spec']
    for entry in todo:
        name = 'kvtest-' + entry['service']
        live = docker('GET', '/v' + api + '/services/' + name)
        if spec_digest(live['Spec']) != entry['spec_sha256']:
            fail(name + ' changed since it was planned; stop and re-plan. Untouched: ' + ', '.join(remaining))
        spec = entry['update_spec']
        started = (live.get('UpdateStatus') or {}).get('StartedAt')
        path_api = '/v' + api + '/services/' + live['ID'] + '/update'
        with allow_once(api, path_api, spec):
            docker('POST', path_api + '?version=' + str(live['Version']['Index']), spec, auth)
        try:
            wait_update(api, live['ID'], started, image)
            wait_running(api, live['ID'])
        except RuntimeError as error:
            fail(str(error).replace('BLOCKED: ', '') + ' Not yet updated: '
                 + (', '.join(remaining[1:]) or 'none') + '. Rollback record: ' + str(rollback_file))
        remaining.pop(0)
        print('UPDATED: ' + name + '; run verify-worker before the next service', file=sys.stderr)
    if gateway_before is not None and docker('GET', '/v' + api + '/services/kvtest-gateway')['Spec'] != gateway_before:
        fail('Gateway changed during the update; investigate')


def rollback(services, confirm):
    """Server-side rollback to each service's PreviousSpec, Gateway first. Dry-run by default."""
    names = ordered(services, reverse=True)
    api = manager_checks()
    existing = {s['Spec']['Name']: s for s in docker('GET', '/v' + api + '/services')}
    steps = []
    for service in names:
        live = existing.get('kvtest-' + service)
        if not live:
            fail('kvtest-' + service + ' is not deployed')
        previous = live.get('PreviousSpec')
        target = live_image(previous or {})
        if not previous or not IMAGE_RE.fullmatch(target):
            fail('kvtest-' + service + ' has no previous spec; re-pin with update and the prior approved digest')
        safe_spec(live['Spec'])
        steps.append((service, live, target))
    for service, live, target in steps:
        print('ROLLBACK PLAN: kvtest-' + service + ' ' + live_image(live['Spec']) + ' -> ' + target, file=sys.stderr)
    print('Schema is NOT rolled back; restore from the approved restore point if migrations must be reversed.',
          file=sys.stderr)
    if confirm is None:
        print('DRY RUN: add --confirm-rollback ' + ','.join(names) + ' to apply', file=sys.stderr)
        return
    if confirm.split(',') != names:
        fail('--confirm-rollback must list exactly the planned services, in order: ' + ','.join(names))
    for service, live, target in steps:
        spec = live['Spec']
        started = (live.get('UpdateStatus') or {}).get('StartedAt')
        path_api = '/v' + api + '/services/' + live['ID'] + '/update'
        # The previous image is already cached on the worker, so no registry credential is needed.
        with allow_once(api, path_api, spec):
            docker('POST', path_api + '?version=' + str(live['Version']['Index']) + '&rollback=previous', spec)
        wait_update(api, live['ID'], started, target, rollback=True)
        wait_running(api, live['ID'])
        print('ROLLED BACK: kvtest-' + service + '; run verify-worker', file=sys.stderr)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_check(origin, path, *, ca=None, token=None, method='GET', data=None, host=None, internal=False):
    context = ssl.create_default_context(cafile=ca)
    handlers = [HTTPSHandler(context=context), NoRedirect()]
    if internal:
        handlers.append(ProxyHandler({}))
    opener = build_opener(*handlers)
    headers = {'Content-Type': 'application/json', 'User-Agent': 'KoloVibe-API-Verification/1.0'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if host:
        headers['Host'] = host
    request = Request(origin + path, method=method, headers=headers, data=data)
    try:
        with opener.open(request, timeout=12) as response:
            status, raw = response.status, response.read(1_000_001)
    except HTTPError as error:
        try:
            status, raw = error.code, error.read(1_000_001)
        finally:
            error.close()
    if len(raw) > 1_000_000:
        fail('Oversized response')
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        body = None
    return status, body


def record(rows, name, call, expected, contract=None):
    try:
        status, body = call()
        passed = status in expected and (contract is None or contract(body))
        rows.append({'test': name, 'status': 'PASS' if passed else 'FAIL', 'http': status,
                     'expected_http': list(expected)})
    except Exception as error:
        rows.append({'test': name, 'status': 'FAIL', 'error_type': type(error).__name__})


def container_tests(service):
    """Executed inside the selected service; secrets never leave this process."""
    sys.path.insert(0, '/app/services/' + service)
    sys.path.insert(0, '/app/services')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'service.settings')
    import django
    django.setup()
    from django.db import connection
    rows = []
    ca = os.environ['KOLOVIBE_INTERNAL_CA_FILE']
    origin = 'https://' + service + ':8000'
    def call(path, **kw):
        return https_check(origin, path, ca=ca, internal=True, **kw)
    ok = lambda b: b == {'status': 'ok'}
    for path in ('/health/live', '/health/ready'):
        record(rows, path, lambda p=path: call(p), (200,), ok)
    token = Path(os.environ['KOLOVIBE_PROBE_TOKEN_FILE']).read_text().strip()
    record(rows, 'protected probe', lambda: call('/ops/verify', token=token), (200,), ok)
    record(rows, 'probe denies missing token', lambda: call('/ops/verify'), (403,))
    record(rows, 'probe denies invalid token', lambda: call('/ops/verify', token='invalid'), (403,))
    record(rows, 'internal denies unsigned caller', lambda: call('/internal/probe'), (403,))
    record(rows, 'wrong Host rejected', lambda: call('/health/live', host='evil.example.test'), (400,))
    record(rows, 'liveness POST rejected', lambda: call('/health/live', method='POST', data=b'{}'), (405,))
    for path in ('/admin', '/api/v1/points', '/api/v1/auth/login'):
        record(rows, 'gated ' + path, lambda p=path: call(p), (403,))
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user,current_schema(),current_database(), '
                           '(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())')
            user, schema, database, tls = cursor.fetchone()
            if (user, schema, database, tls) != ('kv_' + service + '_run', service, 'kolovibe_staging', True):
                raise ValueError('Unexpected database identity')
            if connection.settings_dict['OPTIONS']['sslmode'] != 'verify-full':
                raise ValueError('Database TLS identity disabled')
            cursor.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user')
            if cursor.fetchone() != (False, False, False):
                raise ValueError('Privileged runtime login')
            for other in SERVICES:
                if other != service:
                    cursor.execute('SELECT has_schema_privilege(current_user,%s,\'USAGE\')', [other])
                    if cursor.fetchone()[0]:
                        raise ValueError('Cross-schema access')
        rows.append({'test': 'database TLS identity/schema isolation', 'status': 'PASS'})
    except Exception as error:
        rows.append({'test': 'database TLS identity/schema isolation', 'status': 'FAIL', 'error_type': type(error).__name__})
    if service == 'gateway':
        public_tests(rows, call)
        signed_tests(rows, ca)
    return {'service': service, 'checks': rows}


def signed_tests(rows, ca):
    import hmac
    from urllib.parse import urlsplit
    peers = json.loads(Path(os.environ['KOLOVIBE_TRUSTED_PEERS_FILE']).read_text())
    key = Path(os.environ['KOLOVIBE_OUTBOUND_KEY_FILE']).read_text().strip()
    for peer in ('content', 'creators'):
        try:
            origin = peers[peer].rstrip('/')
            parsed = urlsplit(origin)
            if (parsed.scheme != 'https' or parsed.hostname != peer or parsed.port != 8000
                    or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
                raise ValueError('Peer origin differs from service DNS contract')
            nonce, stamp = secrets.token_urlsafe(24), str(int(time.time()))
            path = '/internal/probe'
            canonical_request = '\n'.join(('gateway', peer, stamp, nonce, 'GET', path, hashlib.sha256(b'').hexdigest()))
            signature = hmac.new(key.encode(), canonical_request.encode(), hashlib.sha256).hexdigest()
            headers = {'X-KoloVibe-Caller': 'gateway', 'X-KoloVibe-Timestamp': stamp,
                       'X-KoloVibe-Nonce': nonce, 'X-KoloVibe-Signature': signature}
            opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=ca)), NoRedirect())
            def send():
                try:
                    with opener.open(Request(origin + path, headers=headers), timeout=12) as response:
                        return response.status, json.loads(response.read(1024))
                except HTTPError as error:
                    error.close()
                    return error.code, None
            record(rows, peer + ' signed TLS/DNS/readiness', send, (200,), lambda b: b == {'status': 'ok'})
            record(rows, peer + ' nonce replay rejected', send, (403,))
            headers['X-KoloVibe-Nonce'] = secrets.token_urlsafe(24)
            headers['X-KoloVibe-Signature'] = '0'*64
            record(rows, peer + ' forged signature rejected', send, (403,))
        except Exception as error:
            rows.append({'test': peer + ' signed transport', 'status': 'FAIL', 'error_type': type(error).__name__})


def public_tests(rows, call, collect=record):
    collect(rows, 'video list contract', lambda: call('/api/v1/videos'), (200,),
           lambda b: isinstance(b, dict) and set(b) == {'items', 'next_cursor'}
           and isinstance(b['items'], list) and len(b['items']) <= 20)
    collect(rows, 'invalid cursor', lambda: call('/api/v1/videos?cursor=invalid'), (400,))
    collect(rows, 'unexpected query rejected', lambda: call('/api/v1/videos?unsupported=1'), (400,))
    unknown = '00000000-0000-4000-8000-' + secrets.token_hex(6)
    for path in ('/api/v1/videos/', '/api/v1/creators/'):
        collect(rows, 'unknown ' + path, lambda p=path: call(p + unknown), (404,),
               lambda b: isinstance(b, dict) and b.get('detail') == 'Not found')
    collect(rows, 'video mutation denied', lambda: call('/api/v1/videos', method='POST', data=b'{}'), (403,))
    for name in ('register', 'verify', 'login', 'refresh', 'logout', 'mfa/verify'):
        collect(rows, 'account gate ' + name, lambda n=name: call('/api/v1/auth/' + n, method='POST', data=b'{}'), (403,))
    collect(rows, 'account me gate', lambda: call('/api/v1/me'), (403,))


def container_id(service):
    ids = run(['docker', 'ps', '--filter', 'label=com.docker.swarm.service.name=kvtest-' + service,
               '--filter', 'status=running', '--format', '{{.ID}}']).splitlines()
    if len(ids) != 1:
        fail('Expected one running container for ' + service)
    return ids[0]


def inside(service, mode, image):
    cid = container_id(service)
    info = json.loads(run(['docker', 'inspect', cid]))[0]
    running = info['Config']['Image']
    if running != image if image else not IMAGE_RE.fullmatch(running):
        fail('Container digest differs: ' + service)
    # Source is sent through stdin, no file or secret copy inside the container.
    source = Path(__file__).read_text()
    code = source + '\nprint(json.dumps(container_tests(' + repr(service) + ')))\n' if mode == 'tests' else (
        source + '\nprint(json.dumps(https_check("https://gateway:8000", "/health/live", '
        'ca=os.environ["KOLOVIBE_INTERNAL_CA_FILE"], internal=True)))\n')
    return json.loads(run(['docker', 'exec', '-i', cid, 'python', '-c',
                          'import sys; exec(compile(sys.stdin.read(), "<cluster-probe>", "exec"), {"__name__":"cluster_probe"})'],
                         data=code, timeout=240))


def worker_preflight():
    root('vm-swarm-worker')
    guard = json.loads(run(['python3', '/usr/local/sbin/kolovibe_db_route_fix.py', '--worker-evidence']))
    if guard.get('guard') is not True or guard.get('db') != '10.0.2.103':
        fail('Working bridge guard is not verified')
    live = inside('gateway', 'live', None)
    if live != [200, {'status': 'ok'}]:
        fail('Existing Gateway HTTPS liveness failed')
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return {'kind': 'KVB-CLUSTER-WORKER-V1', 'host': 'vm-swarm-worker', 'time': int(time.time()),
            'guard': True, 'gateway_live': True,
            'available_memory_bytes': int(memory['MemAvailable'].split()[0])*1024}


def verify_worker(image, services=SERVICES):
    """Verify `services` (all by default) are running exactly `image`; a staged rollout
    verifies each service as it moves, so the rest are not claimed."""
    root('vm-swarm-worker')
    reports = []
    for service in services:
        try:
            reports.append(inside(service, 'tests', image))
        except Exception as error:
            reports.append({'service': service, 'checks': [{'test': 'container probe', 'status': 'FAIL',
                                                          'error_type': type(error).__name__}]})
    broker_ids = run(['docker', 'ps', '--filter', 'status=running', '--format', '{{.ID}} {{.Label "com.docker.swarm.service.name"}}']).splitlines()
    broker_ids = [line.split()[0] for line in broker_ids if re.search(r'(?:_|-)rabbitmq$', line)]
    broker = {'service': 'rabbitmq', 'checks': []}
    if len(broker_ids) == 1:
        for command in ('ping', 'check_running', 'check_local_alarms', 'check_virtual_hosts'):
            try:
                run(['docker', 'exec', broker_ids[0], 'rabbitmq-diagnostics', '-q', command])
                broker['checks'].append({'test': command, 'status': 'PASS'})
            except Exception as error:
                broker['checks'].append({'test': command, 'status': 'FAIL', 'error_type': type(error).__name__})
    else:
        broker['checks'].append({'test': 'one running broker', 'status': 'FAIL'})
    reports.append(broker)
    return {'scope': 'private-deployed-services', 'time': datetime.now(timezone.utc).isoformat(),
            'image': image, 'services_checked': list(services), 'reports': reports,
            'not_tested': ['live account flows (gated)', 'unfinished business APIs',
                           'AMQP publish/consume and Celery integration', 'external ingress',
                           'backup/restore and failover']}


def verify_edge():
    jobs = []
    def collect(_rows, name, call, expected, contract=None):
        jobs.append((name, call, expected, contract))
    def call(path, **kw):
        return https_check('https://api.cabetechs.shop', path, **kw)
    for path in ('/health/live', '/health/ready'):
        collect(None, path, lambda p=path: call(p), (200,), lambda b: b == {'status': 'ok'})
    public_tests(None, call, collect=collect)
    for path in ('/internal/probe', '/admin', '/ops/verify', '/api/v1/points'):
        collect(None, 'public negative ' + path, lambda p=path: call(p), (401, 403, 404))
    def check(job):
        rows = []
        record(rows, *job)
        return rows[0]
    with ThreadPoolExecutor(max_workers=4) as executor:
        rows = list(executor.map(check, jobs))
    return {'scope': 'public-api', 'time': datetime.now(timezone.utc).isoformat(), 'origin': 'https://api.cabetechs.shop',
            'checks': rows, 'not_tested': ['private service health', 'live account success flows',
                                           'unimplemented business routes', 'Cloudflare access policy']}


def has_failures(report):
    rows = report.get('checks', []) + [row for item in report.get('reports', []) for row in item['checks']]
    return any(row['status'] != 'PASS' for row in rows)


def cloud_run(username, image, revision):
    """Use the operator's existing Cloud Shell SSH aliases, never copy SSH keys."""
    if not username or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', username):
        fail('Supply --registry-user with the GitHub registry username')
    source = Path(__file__).resolve()
    destination = '/home/ubuntu/kolovibe_cluster.py'
    output = Path('kolovibe-evidence-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    output.mkdir(mode=0o700)
    for host in ('swarm-manager', 'swarm-worker'):
        run(['scp', str(source), host + ':' + destination], timeout=60)
    worker = run(['ssh', 'swarm-worker', 'sudo python3 ' + destination + ' worker-preflight'], timeout=60)
    evidence = output / 'worker-preflight.json'
    json.loads(worker)
    evidence.write_text(worker)
    remote_evidence = '/home/ubuntu/kolovibe-cluster-evidence.json'
    run(['scp', str(evidence), 'swarm-manager:' + remote_evidence], timeout=60)
    result = subprocess.call(['ssh', '-t', 'swarm-manager', 'sudo python3 ' + destination
                              + ' deploy --worker-evidence ' + remote_evidence + ' --registry-user ' + username
                              + ' --image ' + image + ' --revision ' + revision])
    # Even a partially blocked deployment gets an honest private/public report.
    command = ['ssh', 'swarm-worker', 'sudo python3 ' + destination + ' verify-worker --image ' + image]
    checked = subprocess.run(command, capture_output=True, text=True, timeout=1200)
    if checked.stdout:
        try:
            private = json.loads(checked.stdout)
        except ValueError:
            private = {'status': 'FAIL', 'reason': 'worker report was unavailable'}
    else:
        private = {'status': 'FAIL', 'reason': 'worker report was unavailable'}
    (output / 'private-api.json').write_text(json.dumps(private, indent=2) + '\n')
    public = verify_edge()
    (output / 'public-api.json').write_text(json.dumps(public, indent=2) + '\n')
    summary = {'image': image, 'revision': revision, 'deployment_exit_code': result, 'private_checks_exit_code': checked.returncode,
               'public_failed_checks': sum(r['status'] != 'PASS' for r in public['checks']),
               'gateway_database_dns_firewall_nginx': 'unchanged', 'evidence_directory': str(output),
               'full_acceptance': False}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    if result or checked.returncode or has_failures(public):
        sys.exit(2)


def csv(value):
    return [item for item in (value or '').split(',') if item]


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('cloud-run', 'worker-preflight', 'plan', 'deploy', 'update-plan', 'update',
                                         'rollback', 'verify-worker', 'verify-edge'))
    parser.add_argument('--worker-evidence')
    parser.add_argument('--registry-user')
    parser.add_argument('--release-dir', help='downloaded published-image-<sha> CI artifact (preferred)')
    parser.add_argument('--image', help=REPOSITORY + '@sha256:<digest>; never defaulted')
    parser.add_argument('--revision', help='40-hex commit the image was built from')
    parser.add_argument('--services', help='comma-separated, explicit; never defaulted')
    parser.add_argument('--restore-point-ref', help='identifier of the owner-approved restore point')
    parser.add_argument('--confirm-image', help='repeat the approved digest to apply an update')
    parser.add_argument('--confirm-rollback', help='repeat the planned service list to apply a rollback')
    parser.add_argument('--rollback-file', help='new private file recording the pre-update state')
    parser.add_argument('--accept-ungated', action='store_true',
                        help='update services with no healthcheck; verify-worker/verify-edge must follow')
    args = parser.parse_args()
    if args.mode in ('plan', 'deploy', 'update-plan', 'update', 'cloud-run'):
        image, revision = resolve_release(args.image, args.revision, args.release_dir)
    if args.mode == 'cloud-run':
        cloud_run(args.registry_user, image, revision)
        return
    if args.mode in ('plan', 'deploy', 'update-plan', 'update') and not args.worker_evidence:
        parser.error('--worker-evidence is required')
    if args.mode in ('plan', 'deploy'):
        deploy(args.worker_evidence, args.registry_user, image, revision, dry_run=args.mode == 'plan')
        return
    if args.mode in ('update-plan', 'update'):
        confirm = args.confirm_image if args.mode == 'update' else None
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        update(args.worker_evidence, args.registry_user, image, revision, csv(args.services),
               args.restore_point_ref, confirm, args.rollback_file or 'kolovibe-rollback-' + stamp + '.json',
               args.accept_ungated)
        return
    if args.mode == 'rollback':
        rollback(csv(args.services), args.confirm_rollback)
        return
    if args.mode == 'verify-worker':
        if not args.image or not IMAGE_RE.fullmatch(args.image):
            parser.error('--image must be the expected immutable digest')
        selected = csv(args.services) or list(SERVICES)
        if set(selected) - set(SERVICES):
            parser.error('--services must be a subset of ' + ', '.join(SERVICES))
        report = verify_worker(args.image, selected)
    else:
        report = worker_preflight() if args.mode == 'worker-preflight' else verify_edge()
    print(json.dumps(report, indent=2))
    if has_failures(report):
        sys.exit(2)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not reveal arbitrary DB/HTTP/registry error strings.
        print(str(error) if isinstance(error, RuntimeError) else 'BLOCKED: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
