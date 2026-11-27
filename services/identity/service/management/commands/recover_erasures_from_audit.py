import json
from urllib.error import URLError

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...erasure import recover
from ...internal_client import signed_internal_request

PATH = "/internal/audit/erasure-recovery"
KINDS = {"account.deactivated", "account.privacy_erasure_completed"}
MAX_PAGES = 10000
MAX_RESPONSE = 262144


def _page(cursor):
    payload = json.dumps({"cursor": cursor} if cursor else {}, separators=(",", ":")).encode()
    with signed_internal_request("audit", PATH, method="POST", payload=payload, timeout=10) as response:
        raw = response.read(MAX_RESPONSE + 1)
        if response.status != 200 or len(raw) > MAX_RESPONSE:
            raise ValueError
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"items", "next_cursor"} or not isinstance(data["items"], list):
        raise ValueError
    for item in data["items"]:
        if (not isinstance(item, dict) or set(item) != {"id", "account_id", "kind", "occurred_at"}
                or item["kind"] not in KINDS or not isinstance(item["account_id"], str)):
            raise ValueError
    return data["items"], data["next_cursor"]


class Command(BaseCommand):
    help = ("Mandate 3.4: after restoring an Identity backup, re-apply every deactivation and completed erasure that "
            "Audit recorded, so a restore cannot bring an erased account back. Idempotent. Run reapply_erasures "
            "--all and the Identity dispatcher next.")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="read and count only; change nothing")

    def handle(self, *args, **options):
        counts = {"restored": 0, "unchanged": 0, "missing": 0}
        cursor, pages = None, 0
        while True:
            try:
                items, cursor = _page(cursor)
            except (URLError, OSError, ValueError, TypeError, KeyError, UnicodeError, RuntimeError):
                raise CommandError("The Audit recovery source is unavailable; nothing further was changed") from None
            for item in items:
                with transaction.atomic():
                    outcome = recover(item["account_id"], item["kind"])
                    if options["dry_run"]:
                        transaction.set_rollback(True)
                counts[outcome] += 1
            pages += 1
            if cursor is None:
                break
            if pages >= MAX_PAGES:
                raise CommandError("The Audit recovery source did not end; stopped")
        # Counts only: no account, email or request detail is printed.
        verb = "Would re-apply" if options["dry_run"] else "Re-applied"
        self.stdout.write(f"{verb} {counts['restored']} recorded facts ({counts['unchanged']} already in place, "
                          f"{counts['missing']} accounts not in this database); run reapply_erasures --all next")
