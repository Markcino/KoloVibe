"""B2 — business verification: requests, text evidence, reviewer decisions, status and revocation.

The mechanism is approved; the policy (evidence checklist, validity period, reason-code vocabulary) is the owner's
and is NOT encoded here. Public visibility is not decided here either: this module only moves business state.
"""
import re
import unicodedata

from django.db import transaction
from django.utils import timezone

from . import authz, limits, listings, security_audit
from .api import Result, operation
from .errors import ApiError, not_found
from .models import Business, VerificationCase, VerificationDecision, VerificationEvidence
from .validation import boolean, clean_text, page_params, parse, uuid_text

CUSTOMER = ("viewer", "creator")
REVIEWERS = ("moderator", "administrator")
OWNER = authz.OWNER
S, C = Business.State, VerificationCase.State

# business state -> states it may move to through verification (one table, one function)
BUSINESS_TRANSITIONS = {
    S.DRAFT: {S.SUBMITTED}, S.NEEDS_INFO: {S.SUBMITTED}, S.REJECTED: {S.SUBMITTED},
    S.SUBMITTED: {S.UNDER_REVIEW}, S.UNDER_REVIEW: {S.NEEDS_INFO, S.VERIFIED, S.REJECTED},
    S.VERIFIED: {S.REVOKED}, S.REVOKED: {S.SUBMITTED},
}
CODE = re.compile(r"[a-z][a-z_]{2,39}")


def move(business, target):
    if target not in BUSINESS_TRANSITIONS.get(business.state, set()):
        raise ApiError(409, "That change is not allowed in the business's current state", "invalid_transition")
    business.state = target
    business.version += 1
    business.save(update_fields=["state", "version"])


def _code(value):
    if not isinstance(value, str) or not CODE.fullmatch(value):
        raise ApiError(400, "Invalid request")
    return value


def _evidence(value):
    if not isinstance(value, list) or not limits.MIN_EVIDENCE_ITEMS <= len(value) <= limits.MAX_EVIDENCE_ITEMS:
        raise ApiError(400, "Invalid request")
    return [parse(item, {"kind": (_code, True), "value": (lambda v: clean_text(v, 2, 300), True)}) for item in value]


def _normal(name):
    name = unicodedata.normalize("NFKD", name).casefold()
    return re.sub(r"[^a-z0-9]", "", name)


def _duplicates(business):
    mine = {_normal(business.display_name), _normal(business.legal_name)}
    found = []
    for other in Business.objects.exclude(pk=business.pk).exclude(state=S.CLOSED).only(
            "id", "display_name", "legal_name").iterator():
        if mine & {_normal(other.display_name), _normal(other.legal_name)}:
            found.append(str(other.id))
        if len(found) == 10:
            break
    return found


def _owner_view(case):
    return {"state": case.state if case else "none",
            "submitted_at": case.submitted_at.isoformat() if case else None,
            "decided_at": case.decided_at.isoformat() if case and case.decided_at else None,
            "reason_code": (case.reason_code or None) if case else None}


def _latest(business):
    return business.verification_cases.order_by("-submitted_at", "-id").first()


def _attach(case, items):
    VerificationEvidence.objects.bulk_create([VerificationEvidence(case=case, **item) for item in items])


@operation("verification_submit", roles=CUSTOMER, idempotent=True, budget="verification_submit")
def verification_submit(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "method": (_code, True),
                          "declaration": (boolean, True), "evidence": (_evidence, True)})
    if fields["declaration"] is not True:
        raise ApiError(400, "Invalid request")
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        if business.verification_cases.filter(state=C.NEEDS_INFO).exists():
            raise ApiError(409, "Answer the open request for information instead", "use_respond")
        move(business, S.SUBMITTED)
        case = VerificationCase.objects.create(business=business, method=fields["method"],
                                               submitted_by_account_id=ctx.actor_id,
                                               duplicate_candidates=_duplicates(business))
        _attach(case, fields["evidence"])
        security_audit.record("business.verification_submitted", ctx.actor_id, "business", business.id)
    return Result(201, _owner_view(case))


@operation("verification_respond", roles=CUSTOMER, idempotent=True, budget="verification_submit")
def verification_respond(ctx, data):
    """Owner answers a request for information: adds evidence and returns the case to review."""
    fields = parse(data, {"business_id": (uuid_text, True), "evidence": (_evidence, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        case = business.verification_cases.select_for_update().filter(state=C.NEEDS_INFO).first()
        if case is None:
            raise ApiError(409, "No request for information is open", "no_open_request")
        move(business, S.SUBMITTED)
        case.state, case.assigned_reviewer_account_id = C.SUBMITTED, None
        case.save(update_fields=["state", "assigned_reviewer_account_id"])
        _attach(case, fields["evidence"])
        security_audit.record("business.verification_responded", ctx.actor_id, "business", business.id)
    return Result(200, _owner_view(case))


@operation("verification_status", roles=CUSTOMER, budget="read")
def verification_status(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))  # staff: 404
    return Result(200, _owner_view(_latest(business)))


# ---- reviewers ------------------------------------------------------------------------------------------------------
def _case_for_reviewer(ctx, case_id, *, lock=False):
    query = VerificationCase.objects.select_related("business").filter(pk=case_id)
    if lock:
        query = query.select_for_update(of=("self",))
    case = query.first()
    # No grant, or a case outside the grant, looks exactly like an unknown case.
    if case is None or not authz.has_grant(ctx.actor_id, "verification", case.business_id):
        raise not_found()
    return case


def _conflict_of_interest(ctx, case):
    return case.submitted_by_account_id == ctx.actor_id or authz.is_affiliated(ctx.actor_id, case.business)


@operation("verification_queue", roles=REVIEWERS, mfa=True, budget="read")
def verification_queue(ctx, data):
    cursor, limit = page_params(parse(data, {"cursor": (lambda v: v, False), "limit": (lambda v: v, False)}),
                                limits.PAGE_SIZE)
    everything, targets = authz.granted_targets(ctx.actor_id, "verification")
    query = VerificationCase.objects.select_related("business").filter(state__in=VerificationCase.OPEN).order_by("id")
    if not everything:
        query = query.filter(business_id__in=targets)
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = list(query[:limit + 1])
    with transaction.atomic():
        security_audit.record("business.verification_queue_read", ctx.actor_id, "account", ctx.actor_id)
    items = [{"case_id": str(c.id), "business_id": str(c.business_id), "display_name": c.business.display_name,
              "state": c.state, "submitted_at": c.submitted_at.isoformat(),
              "assigned_to_you": c.assigned_reviewer_account_id == ctx.actor_id} for c in page[:limit]]
    return Result(200, {"items": items, "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


@operation("verification_case", roles=REVIEWERS, mfa=True, budget="read")
def verification_case(ctx, data):
    fields = parse(data, {"case_id": (uuid_text, True)})
    case = _case_for_reviewer(ctx, fields["case_id"])
    if _conflict_of_interest(ctx, case):
        raise not_found()
    with transaction.atomic():
        security_audit.record("business.verification_case_read", ctx.actor_id, "business", case.business_id)
    business = case.business
    candidates = list(Business.objects.filter(pk__in=case.duplicate_candidates).values("id", "display_name", "state"))
    return Result(200, {
        "case_id": str(case.id), "business_id": str(business.id), "state": case.state, "method": case.method,
        "display_name": business.display_name, "legal_name": business.legal_name,
        "submitted_at": case.submitted_at.isoformat(), "assigned_to_you": case.assigned_reviewer_account_id == ctx.actor_id,
        "evidence": [{"id": str(e.id), "kind": e.kind, "value": e.value}
                     for e in case.evidence.order_by("created_at", "id")],
        "duplicate_candidates": [{"business_id": str(c["id"]), "display_name": c["display_name"], "state": c["state"]}
                                 for c in candidates]})


@operation("verification_claim", roles=REVIEWERS, mfa=True, idempotent=True)
def verification_claim(ctx, data):
    fields = parse(data, {"case_id": (uuid_text, True)})
    with transaction.atomic():
        case = _case_for_reviewer(ctx, fields["case_id"], lock=True)
        if _conflict_of_interest(ctx, case):
            raise not_found()
        business = Business.objects.select_for_update().get(pk=case.business_id)
        if case.state != C.SUBMITTED:
            raise ApiError(409, "The case is not waiting for a reviewer", "invalid_transition")
        move(business, S.UNDER_REVIEW)
        case.state, case.assigned_reviewer_account_id = C.UNDER_REVIEW, ctx.actor_id
        case.save(update_fields=["state", "assigned_reviewer_account_id"])
        security_audit.record("business.verification_claimed", ctx.actor_id, "business", business.id)
    return Result(200, {"case_id": str(case.id), "state": case.state})


@operation("verification_decide", roles=REVIEWERS, mfa=True, idempotent=True)
def verification_decide(ctx, data):
    fields = parse(data, {"case_id": (uuid_text, True), "decision": (lambda v: v, True), "reason_code": (_code, True),
                          "note": (lambda v: clean_text(v, 0, 500, multiline=True), False)})
    if fields["decision"] not in limits.REVIEWER_DECISIONS:
        raise ApiError(400, "Invalid request")
    with transaction.atomic():
        case = _case_for_reviewer(ctx, fields["case_id"], lock=True)
        if _conflict_of_interest(ctx, case):
            raise not_found()
        business = Business.objects.select_for_update().get(pk=case.business_id)
        decision = fields["decision"]
        if decision == "revoke":
            if case.state != C.VERIFIED:
                raise ApiError(409, "Only a verified business can be revoked", "invalid_transition")
            target_business, target_case = S.REVOKED, C.REVOKED
        else:
            if case.state != C.UNDER_REVIEW or case.assigned_reviewer_account_id != ctx.actor_id:
                raise ApiError(409, "Claim the case before deciding it", "claim_required")
            target_business, target_case = {"verify": (S.VERIFIED, C.VERIFIED), "reject": (S.REJECTED, C.REJECTED),
                                            "request_info": (S.NEEDS_INFO, C.NEEDS_INFO)}[decision]
        move(business, target_business)
        case.state, case.reason_code, case.decided_at = target_case, fields["reason_code"], timezone.now()
        case.save(update_fields=["state", "reason_code", "decided_at"])
        VerificationDecision.objects.create(case=case, decided_by_account_id=ctx.actor_id, decision=decision,
                                            reason_code=fields["reason_code"], note=fields.get("note", ""))
        listings.refresh(business)  # a revocation removes the listing in the same transaction
        security_audit.record("business.verification_decided", ctx.actor_id, "business", business.id)
    return Result(200, {"case_id": str(case.id), "state": case.state, "business_state": business.state})


@operation("reviewer_grant", roles=("administrator",), mfa=True, idempotent=True)
def reviewer_grant(ctx, data):
    fields = parse(data, {"reviewer_account_id": (uuid_text, True), "scope": (lambda v: v, True),
                          "target_business_id": (lambda v: None if v is None else uuid_text(v), False),
                          "active": (boolean, True)})
    if fields["scope"] not in ("verification", "review_queue", "profile_review"):
        raise ApiError(400, "Invalid request")
    if fields["reviewer_account_id"] == ctx.actor_id:
        raise ApiError(409, "Administrators cannot grant themselves", "self_grant")
    target = fields.get("target_business_id")
    with transaction.atomic():
        if target is not None and not Business.objects.filter(pk=target).exists():
            raise not_found()
        grant = authz.put_grant(fields["reviewer_account_id"], fields["scope"], target, fields["active"], ctx.actor_id)
        security_audit.record("business.reviewer_grant_changed", ctx.actor_id, "account", fields["reviewer_account_id"])
    return Result(200, {"id": str(grant.id), "scope": grant.scope, "active": grant.active})
