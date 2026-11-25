"""The approved R1 staging capability policy (fail closed, one place).

Every capability is off unless it is named in KOLOVIBE_STAGING_CAPABILITIES, a comma-separated list
that must be exactly sorted, free of duplicates and made only of the names below. A service may carry
only the capabilities that apply to it; the configuration refuses anything else, so a flag copied to the
wrong service stops that service at start-up instead of widening it.

Routes are allowed by explicit (service, capability, method, path) rules. Nothing is derived from a
service's URL table, so a route added to a service stays closed in staging until a rule names it here;
`scripts/test_staging_capabilities.py` checks that every registered route is covered and that every rule
is reachable. Reviewer and administrative routes are `privileged`: they are additionally closed unless the
MFA capability (`KOLOVIBE_STAGING_PRIVILEGED=1`) is on, and the MFA, RBAC and audit checks that exist in
Identity and the Gateway stay the authority; this module only decides whether a route is reachable at all.
"""

import re

SERVICES = ("gateway", "identity", "creators", "content", "engagement", "points", "moderation", "audit")
CAPABILITIES = ("account_management", "analytics", "audit_read", "engagement", "media", "moderation", "points", "watch")

# Which capabilities each service may carry. Creator onboarding keeps its own, older flag.
APPLICABLE = {
    "gateway": frozenset(CAPABILITIES),
    "identity": frozenset({"account_management", "moderation"}),
    "creators": frozenset({"media"}),
    "content": frozenset({"analytics", "engagement", "media", "moderation"}),
    "engagement": frozenset({"analytics", "engagement", "points", "watch"}),
    "points": frozenset({"points"}),
    "moderation": frozenset({"moderation"}),
    "audit": frozenset({"audit_read"}),
    # Business carries no Gateway capability yet: its own flags stay closed and nothing is reachable through it.
    "business": frozenset(),
}

# A capability cannot be on without the ones it needs (checked on the whole set, on every service).
REQUIRES = {
    "audit_read": frozenset({"account_management", "moderation"}),
    "analytics": frozenset({"engagement", "media"}),
    "points": frozenset({"engagement"}),
    "watch": frozenset({"media", "points"}),
}

# Peers the Gateway must be able to reach for each capability (its trusted-peers file must equal the union).
GATEWAY_PEERS = {
    "audit_read": frozenset({"audit", "identity"}),
    "account_management": frozenset({"identity"}),
    "analytics": frozenset({"content", "engagement"}),
    "engagement": frozenset({"engagement"}),
    "media": frozenset({"content"}),
    "moderation": frozenset({"content", "identity", "moderation"}),
    "points": frozenset({"engagement", "points"}),
    "watch": frozenset({"content", "engagement"}),
}

# Peers a receiver itself calls (its trusted-peers file) when it carries the capability.
RECEIVER_PEERS = {
    ("moderation", "moderation"): frozenset({"audit", "content"}),
    ("points", "points"): frozenset({"audit"}),
}

UUID = r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
OP = r"[a-z][a-z0-9-]{0,40}"


class Rule:
    __slots__ = ("service", "capability", "methods", "pattern", "privileged")

    def __init__(self, service, capability, methods, pattern, privileged=False):
        self.service, self.capability, self.privileged = service, capability, privileged
        self.methods = frozenset(methods.split())
        self.pattern = re.compile(pattern)


def _rules():
    r = []

    def add(service, capability, methods, *patterns, privileged=False):
        r.extend(Rule(service, capability, methods, p, privileged) for p in patterns)

    # ---- Gateway: the public mobile API -------------------------------------------------------------
    add("gateway", "account_management", "GET", r"/api/v1/app/compatibility", r"/api/v1/me/sessions",
        r"/api/v1/me/preferences", r"/api/v1/me/privacy-requests")
    add("gateway", "account_management", "POST", r"/api/v1/auth/verification/resend",
        r"/api/v1/auth/password/reset-request", r"/api/v1/auth/password/reset", r"/api/v1/me/reauthenticate",
        r"/api/v1/me/step-up", r"/api/v1/me/preferences", r"/api/v1/me/privacy-requests")
    add("gateway", "account_management", "PATCH", r"/api/v1/me", r"/api/v1/me/password", r"/api/v1/me/preferences")
    add("gateway", "account_management", "DELETE", rf"/api/v1/me/sessions/{UUID}")
    add("gateway", "account_management", "GET POST", r"/api/v1/admin/moderator-invitations", privileged=True)
    add("gateway", "account_management", "POST", r"/api/v1/admin/accounts/lookup", privileged=True)
    add("gateway", "account_management", "POST", rf"/api/v1/admin/moderator-invitations/{UUID}/revoke",
        r"/api/v1/auth/moderator-invitations/(?:setup|complete)", privileged=True)
    add("gateway", "media", "GET", r"/api/v1/creators/me", r"/api/v1/creators/me/videos",
        rf"/api/v1/creators/me/videos/{UUID}", rf"/api/v1/videos/{UUID}/playback", rf"/api/v1/videos/{UUID}/upload-status")
    add("gateway", "media", "PATCH", r"/api/v1/creators/me", rf"/api/v1/videos/{UUID}")
    add("gateway", "media", "DELETE", rf"/api/v1/videos/{UUID}")
    add("gateway", "media", "POST", r"/api/v1/videos", rf"/api/v1/videos/{UUID}/upload-intents", rf"/api/v1/videos/{UUID}/upload-status",
        rf"/api/v1/videos/{UUID}/(?:publish|unpublish)")
    # Decision F (D-8): a creator reads and appeals their own measures; administrators manage them.
    add("gateway", "media", "GET", r"/api/v1/creators/me/restrictions")
    add("gateway", "media", "POST", rf"/api/v1/creators/me/restrictions/{UUID}/appeals")
    add("gateway", "media", "GET POST", rf"/api/v1/admin/creators/{UUID}/restrictions", privileged=True)
    add("gateway", "media", "POST", rf"/api/v1/admin/creator-restrictions/{UUID}/lift",
        rf"/api/v1/admin/creator-restriction-appeals/{UUID}/decision", privileged=True)
    add("gateway", "media", "GET", r"/api/v1/admin/creator-restriction-appeals", privileged=True)
    add("gateway", "analytics", "GET", r"/api/v1/creators/me/analytics", rf"/api/v1/creators/me/videos/{UUID}/analytics")
    add("gateway", "engagement", "GET PUT DELETE", rf"/api/v1/videos/{UUID}/like", rf"/api/v1/creators/{UUID}/follow")
    add("gateway", "engagement", "GET", r"/api/v1/videos/following")
    add("gateway", "engagement", "POST", rf"/api/v1/videos/{UUID}/shares")
    add("gateway", "points", "GET", r"/api/v1/creators/me/points", r"/api/v1/creators/me/points/entries",
        rf"/api/v1/creators/me/points/entries/{UUID}")
    add("gateway", "points", "GET", r"/api/v1/admin/points/balances", rf"/api/v1/admin/points/accounts/{UUID}", privileged=True)
    add("gateway", "watch", "POST", rf"/api/v1/videos/{UUID}/watch-sessions", r"/api/v1/engagement/watch-events")
    add("gateway", "moderation", "GET", r"/api/v1/me/standing", r"/api/v1/me/reports", rf"/api/v1/me/reports/{UUID}",
        r"/api/v1/me/appeals", rf"/api/v1/me/appeals/{UUID}", rf"/api/v1/creators/me/videos/{UUID}/notice")
    add("gateway", "moderation", "POST", r"/api/v1/reports", rf"/api/v1/videos/{UUID}/appeals", r"/api/v1/copyright/reports", rf"/api/v1/videos/{UUID}/counter-notices")
    add("gateway", "moderation", "GET", r"/api/v1/creators/me/copyright")
    add("gateway", "moderation", "GET", r"/api/v1/moderation/(?:videos|reports|appeals|edits)", privileged=True)
    add("gateway", "moderation", "POST", rf"/api/v1/moderation/(?:videos|reports|appeals|edits)/{UUID}/decisions", privileged=True)
    add("gateway", "moderation", "GET", rf"/api/v1/moderation/(?:videos|reports|appeals|edits)/{UUID}",
        rf"/api/v1/moderation/previews/{UUID}", r"/api/v1/moderation/totals", r"/api/v1/engagement/fraud-holds", privileged=True)

    add("gateway", "moderation", "GET POST", r"/api/v1/admin/moderation/assignments(?:/summary)?", privileged=True)
    add("gateway", "moderation", "GET POST", r"/api/v1/admin/rights-holders", privileged=True)  # Decision E
    add("gateway", "moderation", "POST", rf"/api/v1/admin/rights-holders/{UUID}/revoke", privileged=True)

    add("gateway", "audit_read", "GET", r"/api/v1/admin/audit", privileged=True)
    add("audit", "audit_read", "POST", r"/internal/audit/read")

    # ---- Identity (internal) ----------------------------------------------------------------------
    add("identity", "account_management", "POST", r"/internal/auth/account-lookup", privileged=True)
    add("identity", "account_management", "POST", r"/internal/auth/moderator-invitations",
        r"/internal/auth/moderator-invitations/(?:setup|complete)", privileged=True)
    add("identity", "account_management", "POST",
        r"/internal/auth/(?:verification/resend|password/reset-request|password/reset|password/change|profile"
        r"|reauthenticate|step-up|step-up/consume|preferences|privacy-requests|sessions)")
    add("identity", "moderation", "POST", r"/internal/auth/standing")

    # ---- Creators (internal): the own-profile read and edit behind `/api/v1/creators/me` ---------------
    add("creators", "media", "POST", r"/internal/creators/me")
    # The two onboarding operations the Gateway's media journey needs, as exact literals: the upload-eligibility
    # check (draft, upload intent, upload completion, publish) and the account-to-creator ownership lookup
    # (library, detail, edit, delete, publish/unpublish, upload status). invite/review/pending/submit/status/
    # standing stay behind the separate privileged creator-onboarding flag (KOLOVIBE_STAGING_CREATOR_ONBOARDING).
    add("creators", "media", "POST", r"/internal/creators/onboarding/eligibility",
        r"/internal/creators/onboarding/ownership", r"/internal/creators/onboarding/review_policy")

    # Decision F: enforcement reads and the creator's own measures travel with the media journey; the
    # administrator operations (issue, lift, list, appeal queue, decision) need the privileged switch.
    add("creators", "media", "POST", r"/internal/creators/restrictions/(?:mine|appeal|capabilities)")
    add("creators", "media", "POST", r"/internal/creators/restrictions/(?:issue|lift|list|appeals|decide)",
        privileged=True)

    # ---- Content (internal) -----------------------------------------------------------------------
    add("content", "engagement", "POST", r"/internal/videos/lookup")
    add("content", "media", "POST", rf"/internal/videos/media/{OP}")
    add("content", "analytics", "POST", rf"/internal/videos/analytics/{OP}")
    add("content", "moderation", "POST", rf"/internal/videos/moderation/{OP}")

    # ---- Engagement, Points, Moderation (internal) ---------------------------------------------------
    add("engagement", "engagement", "POST", r"/internal/likes", r"/internal/likes/status", r"/internal/follows",
        r"/internal/follows/membership", r"/internal/engagement/shares",
        r"/internal/engagement/(?:like-counts|play-counts|follower-count|trending)", r"/internal/engagement/fraud-holds")
    add("engagement", "analytics", "POST", r"/internal/engagement/analytics/(?:video|creator)")
    add("engagement", "watch", "POST", rf"/internal/engagement/watch/{OP}")
    add("points", "points", "POST", rf"/internal/points/{OP}", r"/internal/points/admin/(?:balances|account)")
    add("moderation", "moderation", "POST", rf"/internal/moderation/{OP}")
    add("moderation", "moderation", "POST", r"/internal/moderation/(?:review_queue|own_reports|own_report|own_appeals|own_appeal|video_decision|report_decision|appeal_decision|video_detail|report_detail|appeal_detail|fraud_scope|assignment_list|assignment_set|assignment_summary|copyright_report|counter_notice|copyright_status|edit_queue|edit_detail|edit_decision)")
    return tuple(r)


RULES = _rules()


def parse(value):
    """The validated capability set for one service's environment value; raises on any irregularity."""
    if value is None or value == "":
        return frozenset()
    names = value.split(",")
    if any(name not in CAPABILITIES for name in names):
        raise RuntimeError("Unknown staging capability")
    if names != sorted(set(names)):
        raise RuntimeError("Staging capabilities must be unique and sorted")
    return frozenset(names)


def check(service, caps, *, accounts, privileged):
    """Refuse a capability set that does not belong on this service or is missing what it depends on."""
    if service == "gateway" and "audit_read" in caps and (not accounts or not privileged):
        raise RuntimeError("Audit reads require accounts and MFA")
    if service not in APPLICABLE:
        raise RuntimeError("Unknown staging service")
    if caps - APPLICABLE[service]:
        raise RuntimeError("A staging capability does not apply to this service")
    if service == "gateway":
        # The Gateway is the one place the whole set is visible, so dependencies are enforced there; each
        # other service sees only its own slice of the set (see `slice_for`).
        for cap in caps:
            if REQUIRES.get(cap, frozenset()) - caps:
                raise RuntimeError("A staging capability is missing the capability it depends on")
    if caps & {"account_management", "moderation"} and service in ("gateway", "identity") and not accounts:
        raise RuntimeError("Account and moderation capabilities need the account capability")
    if "moderation" in caps and service in ("gateway", "identity") and not privileged:
        raise RuntimeError("The moderation capability needs privileged MFA sessions")


def slice_for(service, caps):
    """What a service should carry, given the Gateway's full set (used by tools, never by a service)."""
    return frozenset(caps) & APPLICABLE[service]


def gateway_peers(caps, accounts):
    peers = {"content", "creators"} | ({"identity"} if accounts else set())
    for cap in caps:
        peers |= GATEWAY_PEERS[cap]
    return peers


def receiver_peers(service, caps):
    peers = set()
    for cap in caps:
        peers |= RECEIVER_PEERS.get((service, cap), frozenset())
    return peers


def allowed(service, caps, method, path, *, privileged=False):
    """True if an enabled capability's explicit rule names this exact method and path."""
    for rule in RULES:
        if (rule.service == service and rule.capability in caps and method in rule.methods
                and (privileged or not rule.privileged) and rule.pattern.fullmatch(path)):
            return True
    return False
