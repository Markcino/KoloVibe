"""B5 (part 2) — reviews, abuse reports and reviewer decisions.

Approved shape (DR-BZ-15/16/17): the eligibility BASIS is stored on every review and shown; fraud signals HOLD a review
for a reviewer instead of publishing it; the business can respond once but can never hide, edit or remove a review;
aggregates are recomputed server-side from published reviews only. Authors are shown pseudonymously. Reviewer decisions
use a Business-local queue for now: generalising the Moderation service (DR-BZ-17 option C) is a separate approval.
"""
import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import authz, limits, listings, security_audit, throttle
from .api import Result, operation, NIL_ACTOR
from .errors import ApiError, not_found
from .models import (Business, BusinessListing, BusinessReport, InquiryMessage, InquiryThread, Review,
                     ReviewAggregate, ReviewInvitation, ReviewResponse)
from .validation import clean_text, page_params, parse, uuid_text

CUSTOMER = ("viewer", "creator")
REVIEWERS = ("moderator", "administrator")
EVERYONE = ("anonymous",) + CUSTOMER + REVIEWERS
OWNER = authz.OWNER
R = Review.State
SYSTEM = UUID(NIL_ACTOR)
CODE = re.compile(r"[a-z][a-z_]{2,39}")
PAGE = {"cursor": (lambda v: v, False), "limit": (lambda v: v, False)}


def _code(value):
    if not isinstance(value, str) or not CODE.fullmatch(value):
        raise ApiError(400, "Invalid request")
    return value


def _rating(value):
    if type(value) is not int or not 1 <= value <= 5:
        raise ApiError(400, "Invalid request")
    return value


def _digest(text):
    normal = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normal.encode()).hexdigest()


def _code_digest(code):
    return hmac.new(settings.SECRET_KEY.encode(), ("review-invite:" + code).encode(), hashlib.sha256).hexdigest()


def recompute(business):
    published = business.reviews.filter(state=R.PUBLISHED)
    count = published.count()
    total = sum(published.values_list("rating", flat=True))
    ReviewAggregate.objects.update_or_create(business=business, defaults={
        "count": count, "rating_sum": total, "updated_at": timezone.now()})


def rating_view(business):
    row = ReviewAggregate.objects.filter(business=business).first()
    count = row.count if row else 0
    minimum = limits.MIN_REVIEWS_FOR_AVERAGE
    average = round(row.rating_sum / count, 2) if row and minimum is not None and count >= max(minimum, 1) else None
    return {"count": count, "average": average}


def _signals(business, author_id, digest, *, exclude=None):
    now = timezone.now()
    reasons = []
    count, window = limits.HOLD_BUSINESS_BURST
    recent = business.reviews.filter(created_at__gte=now - window)
    if exclude is not None:
        recent = recent.exclude(pk=exclude)
    if recent.count() >= count:
        reasons.append("business_burst")
    count, window = limits.HOLD_AUTHOR_BURST
    mine = Review.objects.filter(author_account_id=author_id, created_at__gte=now - window)
    if exclude is not None:
        mine = mine.exclude(pk=exclude)
    if mine.count() >= count:
        reasons.append("author_burst")
    twins = Review.objects.filter(body_digest=digest, created_at__gte=now - limits.HOLD_DUPLICATE_WINDOW)
    if exclude is not None:
        twins = twins.exclude(pk=exclude)
    if digest and twins.exists():
        reasons.append("duplicate_text")
    return reasons


def _open_hold(review):
    BusinessReport.objects.get_or_create(
        reporter_account_id=SYSTEM, subject_type="review", subject_id=review.id, state="open",
        defaults={"business": review.business, "reason_code": "fraud_hold", "details": ",".join(review.hold_reasons)})
    security_audit.record("business.review_held", review.author_account_id, "business", review.business_id)


def _own_view(review):
    return {"id": str(review.id), "business_id": str(review.business_id), "rating": review.rating,
            "title": review.title or None, "body": review.body, "state": review.state, "basis": review.basis,
            "created_at": review.created_at.isoformat(),
            "edited_at": review.edited_at.isoformat() if review.edited_at else None}


def _public_view(review):
    try:
        response = review.response
    except ReviewResponse.DoesNotExist:
        response = None
    visible = response is not None and not response.removed
    return {"id": str(review.id), "rating": review.rating, "title": review.title or None, "body": review.body,
            "author_label": review.author_label, "basis": review.basis,
            "created_at": review.created_at.isoformat(),
            "edited_at": review.edited_at.isoformat() if review.edited_at else None,
            "response": {"body": response.body, "created_at": response.created_at.isoformat()} if visible else None}


# ---- invitations (route D of DR-BZ-15) ------------------------------------------------------------------------------
@operation("review_invite_create", roles=CUSTOMER, idempotent=True, budget="review_invite")
def review_invite_create(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    now = timezone.now()
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        pending = business.review_invitations.filter(redeemed_at__isnull=True, revoked_at__isnull=True,
                                                     expires_at__gt=now).count()
        if pending >= limits.MAX_PENDING_REVIEW_INVITATIONS:
            raise ApiError(409, "Too many open review invitations", "invitation_limit")
        code = secrets.token_urlsafe(24)
        invitation = ReviewInvitation.objects.create(business=business, code_digest=_code_digest(code),
                                                     created_by_account_id=ctx.actor_id,
                                                     expires_at=now + limits.REVIEW_INVITATION_TTL)
        security_audit.record("business.review_invitation_created", ctx.actor_id, "business", business.id)
    return Result(201, {"id": str(invitation.id), "expires_at": invitation.expires_at.isoformat()}, secret={"code": code})


@operation("review_invite_revoke", roles=CUSTOMER, idempotent=True)
def review_invite_revoke(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "invitation_id": (uuid_text, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))
        invitation = business.review_invitations.select_for_update().filter(pk=fields["invitation_id"]).first()
        if invitation is None:
            raise not_found()
        if invitation.redeemed_at is not None:
            raise ApiError(409, "Invitation already used", "invitation_redeemed")
        if invitation.revoked_at is None:
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=["revoked_at"])
            security_audit.record("business.review_invitation_revoked", ctx.actor_id, "business", business.id)
    return Result(200, {"id": str(invitation.id), "state": "revoked"})


# ---- authors ---------------------------------------------------------------------------------------------------------
def _basis(ctx, business, fields):
    """Resolve the eligibility basis from the proof supplied; consume an invitation if one is used."""
    thread_id, code = fields.get("interaction_thread_id"), fields.get("invitation_code")
    if thread_id is not None and code is not None:
        raise ApiError(400, "Invalid request")
    if thread_id is not None:
        thread = InquiryThread.objects.filter(pk=thread_id, business=business, customer_account_id=ctx.actor_id).first()
        if thread is None or thread.customer_confirmed_at is None or thread.business_confirmed_at is None:
            raise ApiError(409, "That conversation is not confirmed by both sides", "interaction_not_confirmed")
        return Review.Basis.INTERACTION_CONFIRMED, thread
    if code is not None:
        invitation = ReviewInvitation.objects.select_for_update().filter(
            code_digest=_code_digest(code), business=business).first()
        now = timezone.now()
        if (invitation is None or invitation.redeemed_at or invitation.revoked_at or invitation.expires_at <= now):
            raise ApiError(404, "Invitation unavailable")
        invitation.redeemed_by_account_id, invitation.redeemed_at = ctx.actor_id, now
        invitation.save(update_fields=["redeemed_by_account_id", "redeemed_at"])
        return Review.Basis.INVITED, None
    return Review.Basis.OPEN, None


@operation("review_create", roles=CUSTOMER, verified_email=True, idempotent=True, budget="review_create")
def review_create(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "rating": (_rating, True),
                          "title": (lambda v: clean_text(v, 0, 100), False),
                          "body": (lambda v: clean_text(v, 10, 2000, multiline=True), True),
                          "interaction_thread_id": (lambda v: None if v is None else uuid_text(v), False),
                          "invitation_code": (lambda v: None if v is None else clean_text(v, 16, 64), False)})
    with transaction.atomic():
        business = Business.objects.select_for_update().filter(pk=fields["business_id"]).first()
        # Unlisted, unknown, own business and affiliated accounts all answer the same 404.
        if (business is None or not BusinessListing.objects.filter(business=business).exists()
                or authz.is_affiliated(ctx.actor_id, business)):
            raise not_found()
        if Review.objects.filter(business=business, author_account_id=ctx.actor_id).exists():
            raise ApiError(409, "You have already reviewed this business", "already_reviewed")
        basis, thread = _basis(ctx, business, fields)
        digest = _digest(fields["body"])
        reasons = _signals(business, ctx.actor_id, digest)
        now = timezone.now()
        review = Review.objects.create(
            business=business, author_account_id=ctx.actor_id, author_label=f"Reviewer {business.reviews.count() + 1}",
            rating=fields["rating"], title=fields.get("title", ""), body=fields["body"], body_digest=digest,
            basis=basis, interaction_thread=thread, hold_reasons=reasons,
            state=R.HELD if reasons else R.PUBLISHED, published_at=None if reasons else now)
        if reasons:
            _open_hold(review)
        recompute(business)
        security_audit.record("business.review_created", ctx.actor_id, "business", business.id)
    return Result(201, _own_view(review))


@operation("review_list_mine", roles=CUSTOMER, budget="read")
def review_list_mine(ctx, data):
    cursor, limit = page_params(parse(data, PAGE), limits.PAGE_SIZE)
    query = Review.objects.filter(author_account_id=ctx.actor_id).order_by("id")
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = list(query[:limit + 1])
    return Result(200, {"items": [_own_view(r) for r in page[:limit]],
                        "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


def _mine(ctx, review_id):
    review = Review.objects.select_for_update().select_related("business").filter(
        pk=review_id, author_account_id=ctx.actor_id).first()
    if review is None:
        raise not_found()
    return review


@operation("review_edit_mine", roles=CUSTOMER, verified_email=True, idempotent=True, budget="review_edit")
def review_edit_mine(ctx, data):
    fields = parse(data, {"review_id": (uuid_text, True), "rating": (_rating, False),
                          "title": (lambda v: clean_text(v, 0, 100), False),
                          "body": (lambda v: clean_text(v, 10, 2000, multiline=True), False)})
    review_id = fields.pop("review_id")
    if not fields:
        raise ApiError(400, "Invalid request")
    with transaction.atomic():
        review = _mine(ctx, review_id)
        if review.state not in (R.PUBLISHED, R.HELD):
            raise ApiError(409, "This review can no longer be edited", "not_editable")
        for name, value in fields.items():
            setattr(review, name, value)
        if "body" in fields:
            review.body_digest = _digest(review.body)
            reasons = _signals(review.business, ctx.actor_id, review.body_digest, exclude=review.pk)
            if reasons and review.state == R.PUBLISHED:  # edits re-enter the checks; a held review stays held
                review.state, review.published_at = R.HELD, None
                review.hold_reasons = reasons
                _open_hold(review)
        review.edited_at = timezone.now()
        review.save()
        recompute(review.business)
        security_audit.record("business.review_edited", ctx.actor_id, "business", review.business_id)
    return Result(200, _own_view(review))


@operation("review_withdraw_mine", roles=CUSTOMER, idempotent=True)
def review_withdraw_mine(ctx, data):
    """The author's own deletion: the text is blanked at once (a mechanism, not a retention schedule)."""
    fields = parse(data, {"review_id": (uuid_text, True)})
    with transaction.atomic():
        review = _mine(ctx, fields["review_id"])
        if review.state == R.WITHDRAWN:
            return Result(200, _own_view(review))
        review.state, review.title, review.body, review.body_digest = R.WITHDRAWN, "", "", ""
        review.save(update_fields=["state", "title", "body", "body_digest"])
        ReviewResponse.objects.filter(review=review).delete()
        BusinessReport.objects.filter(subject_type="review", subject_id=review.id, state="open").update(
            state="decided", decision="keep", decision_reason_code="withdrawn", decided_at=timezone.now())
        recompute(review.business)
        security_audit.record("business.review_withdrawn", ctx.actor_id, "business", review.business_id)
    return Result(200, _own_view(review))


# ---- public and owner ------------------------------------------------------------------------------------------------
@operation("review_list_public", roles=EVERYONE)
def review_list_public(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), **PAGE})
    business_id = fields.pop("business_id")
    if not throttle.allow("public_read", ctx.throttle_key):
        raise ApiError(429, "Too many requests")
    if not BusinessListing.objects.filter(business_id=business_id).exists():
        raise not_found()
    cursor = fields.get("cursor")
    _, limit = page_params({k: v for k, v in fields.items() if k != "cursor"}, limits.PAGE_SIZE)
    digest = hashlib.sha256(str(business_id).encode()).hexdigest()[:16]
    query = Review.objects.select_related("response").filter(business_id=business_id, state=R.PUBLISHED)
    if cursor is not None:
        if not isinstance(cursor, str) or len(cursor) > 512:
            raise ApiError(400, "Invalid request")
        payload = listings._unsign(cursor)
        if payload["f"] != digest:
            raise ApiError(400, "Invalid request")
        from django.db.models import Q
        from django.utils.dateparse import parse_datetime
        stamp = parse_datetime(payload["n"])
        if stamp is None:
            raise ApiError(400, "Invalid request")
        query = query.filter(Q(published_at__lt=stamp) | Q(published_at=stamp, id__lt=payload["i"]))
    page = list(query.order_by("-published_at", "-id")[:limit + 1])
    last = page[limit - 1] if len(page) > limit else None
    token = listings._sign({"f": digest, "t": 0, "n": last.published_at.isoformat(), "i": str(last.id)}) if last else None
    return Result(200, {"items": [_public_view(r) for r in page[:limit]], "next_cursor": token})


@operation("review_respond", roles=CUSTOMER, idempotent=True)
def review_respond(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "review_id": (uuid_text, True),
                          "body": (lambda v: clean_text(v, 2, 1000, multiline=True), True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))
        review = Review.objects.select_for_update().filter(pk=fields["review_id"], business=business).first()
        if review is None:
            raise not_found()
        if review.state != R.PUBLISHED:
            raise ApiError(409, "Only a published review can be answered", "not_published")
        response, created = ReviewResponse.objects.get_or_create(
            review=review, defaults={"author_account_id": ctx.actor_id, "body": fields["body"]})
        if not created:
            if response.removed:
                raise ApiError(409, "This response was removed by a reviewer", "response_removed")
            response.body, response.author_account_id = fields["body"], ctx.actor_id
            response.save(update_fields=["body", "author_account_id"])
        security_audit.record("business.review_responded", ctx.actor_id, "business", business.id)
    return Result(200, {"review_id": str(review.id), "body": response.body, "created_at": response.created_at.isoformat()})


@operation("review_response_delete", roles=CUSTOMER, idempotent=True)
def review_response_delete(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "review_id": (uuid_text, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,))
        response = ReviewResponse.objects.select_for_update().filter(review_id=fields["review_id"],
                                                                      review__business=business).first()
        if response is None:
            raise not_found()
        if response.removed:
            raise ApiError(409, "This response was removed by a reviewer", "response_removed")  # no self-restoring
        response.delete()
        security_audit.record("business.review_responded", ctx.actor_id, "business", business.id)
    return Result(200, {"status": "ok"})


# ---- abuse reports and reviewer decisions ----------------------------------------------------------------------------
def _subject(ctx, subject_type, subject_id):
    """Return (business, author_ids) only when the reporter is allowed to see the subject; otherwise 404."""
    if subject_type == "review":
        review = Review.objects.select_related("business").filter(pk=subject_id, state=R.PUBLISHED).first()
        if review is None or not BusinessListing.objects.filter(business=review.business).exists():
            raise not_found()
        return review.business, {review.author_account_id}
    if subject_type == "review_response":
        response = ReviewResponse.objects.select_related("review__business").filter(pk=subject_id, removed=False).first()
        if (response is None or response.review.state != R.PUBLISHED
                or not BusinessListing.objects.filter(business=response.review.business).exists()):
            raise not_found()
        return response.review.business, {response.author_account_id}
    message = InquiryMessage.objects.select_related("thread__business").filter(pk=subject_id, removed=False).first()
    if message is None:
        raise not_found()
    thread = message.thread
    if thread.customer_account_id != ctx.actor_id and not authz.is_member(ctx.actor_id, thread.business_id):
        raise not_found()  # only participants may report a message
    return thread.business, {message.author_account_id}


@operation("report_create", roles=CUSTOMER, verified_email=True, idempotent=True, budget="report_create")
def report_create(ctx, data):
    fields = parse(data, {"subject_type": (lambda v: v, True), "subject_id": (uuid_text, True), "reason_code": (_code, True),
                          "details": (lambda v: clean_text(v, 0, 1000, multiline=True), False)})
    if fields["subject_type"] not in BusinessReport.Subject.values:
        raise ApiError(400, "Invalid request")
    with transaction.atomic():
        business, authors = _subject(ctx, fields["subject_type"], fields["subject_id"])
        if ctx.actor_id in authors:
            raise ApiError(409, "You cannot report your own content", "own_content")
        if BusinessReport.objects.filter(reporter_account_id=ctx.actor_id, subject_type=fields["subject_type"],
                                         subject_id=fields["subject_id"], state="open").exists():
            raise ApiError(409, "You have already reported this", "already_reported")
        report = BusinessReport.objects.create(reporter_account_id=ctx.actor_id, business=business, **fields)
        security_audit.record("business.report_created", ctx.actor_id, "business", business.id)
    return Result(201, {"id": str(report.id), "state": report.state})


def _report_for_reviewer(ctx, report_id, *, lock=False):
    query = BusinessReport.objects.select_related("business").filter(pk=report_id, state="open")
    if lock:
        query = query.select_for_update(of=("self",))
    report = query.first()
    if (report is None or not authz.has_grant(ctx.actor_id, "review_queue", report.business_id)
            or authz.is_affiliated(ctx.actor_id, report.business) or report.reporter_account_id == ctx.actor_id):
        raise not_found()
    return report


def _subject_content(report):
    if report.subject_type == "review":
        review = Review.objects.filter(pk=report.subject_id).first()
        return None if review is None else {"rating": review.rating, "title": review.title or None, "body": review.body,
                                             "state": review.state, "basis": review.basis, "hold_reasons": review.hold_reasons}
    if report.subject_type == "review_response":
        response = ReviewResponse.objects.filter(pk=report.subject_id).first()
        return None if response is None else {"body": response.body, "removed": response.removed}
    message = InquiryMessage.objects.filter(pk=report.subject_id).first()
    return None if message is None else {"body": message.body, "author_kind": message.author_kind, "removed": message.removed}


@operation("report_queue", roles=REVIEWERS, mfa=True, budget="read")
def report_queue(ctx, data):
    cursor, limit = page_params(parse(data, PAGE), limits.PAGE_SIZE)
    everything, targets = authz.granted_targets(ctx.actor_id, "review_queue")
    query = BusinessReport.objects.select_related("business").filter(state="open").order_by("id")
    if not everything:
        query = query.filter(business_id__in=targets)
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = list(query[:limit + 1])
    with transaction.atomic():
        security_audit.record("business.report_queue_read", ctx.actor_id, "account", ctx.actor_id)
    visible = [r for r in page[:limit] if r.reporter_account_id != ctx.actor_id and not authz.is_affiliated(ctx.actor_id, r.business)]
    return Result(200, {"items": [{"report_id": str(r.id), "subject_type": r.subject_type, "business_id": str(r.business_id),
                                   "reason_code": r.reason_code, "system_hold": r.reporter_account_id == SYSTEM,
                                   "created_at": r.created_at.isoformat()} for r in visible],
                        "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


@operation("report_case", roles=REVIEWERS, mfa=True, budget="read")
def report_case(ctx, data):
    fields = parse(data, {"report_id": (uuid_text, True)})
    report = _report_for_reviewer(ctx, fields["report_id"])
    with transaction.atomic():
        security_audit.record("business.report_case_read", ctx.actor_id, "business", report.business_id)
    return Result(200, {"report_id": str(report.id), "subject_type": report.subject_type, "subject_id": str(report.subject_id),
                        "business_id": str(report.business_id), "reason_code": report.reason_code,
                        "details": report.details, "system_hold": report.reporter_account_id == SYSTEM,
                        "content": _subject_content(report)})


@operation("report_decide", roles=REVIEWERS, mfa=True, idempotent=True)
def report_decide(ctx, data):
    fields = parse(data, {"report_id": (uuid_text, True), "decision": (lambda v: v, True), "reason_code": (_code, True)})
    decision = fields["decision"]
    if decision not in ("remove", "keep"):
        raise ApiError(400, "Invalid request")
    now = timezone.now()
    with transaction.atomic():
        report = _report_for_reviewer(ctx, fields["report_id"], lock=True)
        business = report.business
        if report.subject_type == "review":
            review = Review.objects.select_for_update().filter(pk=report.subject_id).first()
            if review is None or review.author_account_id == ctx.actor_id:
                raise not_found()
            if decision == "remove" and review.state in (R.PUBLISHED, R.HELD):
                review.state, review.removed_by_account_id, review.removed_at = R.REMOVED, ctx.actor_id, now
                review.save(update_fields=["state", "removed_by_account_id", "removed_at"])
            elif decision == "keep" and review.state == R.HELD:  # a reviewer releases a fraud hold
                review.state, review.published_at = R.PUBLISHED, now
                review.save(update_fields=["state", "published_at"])
            recompute(business)
        elif report.subject_type == "review_response":
            ReviewResponse.objects.filter(pk=report.subject_id).update(
                **({"removed": True, "removed_by_account_id": ctx.actor_id} if decision == "remove" else {}))
        else:
            InquiryMessage.objects.filter(pk=report.subject_id).update(**({"removed": True} if decision == "remove" else {}))
        report.state, report.decision, report.decision_reason_code = "decided", decision, fields["reason_code"]
        report.decided_by_account_id, report.decided_at = ctx.actor_id, now
        report.save(update_fields=["state", "decision", "decision_reason_code", "decided_by_account_id", "decided_at"])
        security_audit.record("business.report_decided", ctx.actor_id, "business", business.id)
    return Result(200, {"report_id": str(report.id), "state": report.state, "decision": decision})
