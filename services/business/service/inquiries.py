"""B5 (part 1) — customer inquiries.

Verified-email customers open a thread with a LISTED business (in-platform only, no attachments, no notifications).
The business sees a pseudonymous label, never an account id or email. Blocking is never disclosed to the blocked
customer. Both sides can confirm the interaction as completed, which is one route to review eligibility (DR-BZ-15).
"""
from django.db import transaction
from django.utils import timezone

from . import authz, limits, security_audit, throttle
from .api import Result, operation
from .errors import ApiError, not_found
from .models import Business, BusinessListing, InquiryBlock, InquiryMessage, InquiryThread
from .validation import PAGE, clean_text, code_text, page_params, parse, uuid_text

CUSTOMER = authz.CUSTOMER
OWNER, STAFF = authz.OWNER, authz.STAFF
T = InquiryThread.State


def _body(value):
    return clean_text(value, 1, 1000, multiline=True)


def _messages(thread):
    return [{"id": str(m.id), "author_kind": m.author_kind, "body": None if m.removed else m.body,
             "removed": m.removed, "created_at": m.created_at.isoformat()}
            for m in thread.messages.order_by("created_at", "id")]


def _confirmation(thread):
    return {"customer": thread.customer_confirmed_at is not None, "business": thread.business_confirmed_at is not None}


def customer_view(thread, *, with_messages=True):
    data = {"id": str(thread.id), "business_id": str(thread.business_id), "business_name": thread.business.display_name,
            "state": thread.state, "subject_code": thread.subject_code, "created_at": thread.created_at.isoformat(),
            "confirmed": _confirmation(thread)}
    if with_messages:
        data["messages"] = _messages(thread)
    return data


def business_view(thread, *, with_messages=True):
    data = {"id": str(thread.id), "customer_label": thread.customer_label, "state": thread.state,
            "subject_code": thread.subject_code, "created_at": thread.created_at.isoformat(),
            "confirmed": _confirmation(thread)}
    if with_messages:
        data["messages"] = _messages(thread)
    return data


def _add_message(thread, kind, actor_id, body):
    if thread.message_count >= limits.MAX_MESSAGES_PER_THREAD:
        raise ApiError(409, "This conversation has reached its message limit", "thread_full")
    now = timezone.now()
    InquiryMessage.objects.create(thread=thread, author_kind=kind, author_account_id=actor_id, body=body, created_at=now)
    thread.message_count += 1
    thread.last_message_at = now
    thread.save(update_fields=["message_count", "last_message_at"])


def _mine(ctx, thread_id, *, lock=False):
    query = InquiryThread.objects.select_related("business").filter(pk=thread_id, customer_account_id=ctx.actor_id)
    if lock:
        query = query.select_for_update(of=("self",))
    thread = query.first()
    if thread is None:
        raise not_found()
    return thread


def _business_thread(ctx, business_id, thread_id, roles=(OWNER, STAFF), *, lock=False):
    """The thread must belong to the path's business AND the caller must be a member of that business."""
    business, membership = authz.require_member(ctx.actor_id, business_id, roles)
    query = InquiryThread.objects.filter(pk=thread_id, business=business)
    if lock:
        query = query.select_for_update(of=("self",))
    thread = query.first()
    if thread is None:
        raise not_found()
    thread.business = business
    return thread


# ---- customer ------------------------------------------------------------------------------------------------------
@operation("inquiry_create", roles=CUSTOMER, verified_email=True, idempotent=True, budget="inquiry_create")
def inquiry_create(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "subject_code": (code_text, True), "body": (_body, True)})
    with transaction.atomic():
        listing = BusinessListing.objects.filter(business_id=fields["business_id"]).first()
        business = Business.objects.select_for_update().filter(pk=fields["business_id"]).first()
        # Unlisted, unknown, own business and "blocked" are one answer: a block is never disclosed.
        if (listing is None or business is None or authz.is_member(ctx.actor_id, business.id)
                or business.created_by_account_id == ctx.actor_id
                or InquiryBlock.objects.filter(business=business, customer_account_id=ctx.actor_id).exists()):
            raise not_found()
        if InquiryThread.objects.filter(business=business, customer_account_id=ctx.actor_id, state=T.OPEN).exists():
            raise ApiError(409, "You already have an open conversation with this business", "thread_exists")
        # Counted only for real, eligible attempts, so probing unlisted ids cannot exhaust a business's budget.
        if not throttle.allow("inquiry_business", business.id):
            raise ApiError(429, "Too many requests")
        label = f"Customer {business.inquiry_threads.count() + 1}"
        thread = InquiryThread.objects.create(business=business, customer_account_id=ctx.actor_id, customer_label=label,
                                              subject_code=fields["subject_code"])
        _add_message(thread, "customer", ctx.actor_id, fields["body"])
        security_audit.record("business.inquiry_created", ctx.actor_id, "business", business.id)
    return Result(201, customer_view(thread))


@operation("inquiry_list_mine", roles=CUSTOMER, budget="read")
def inquiry_list_mine(ctx, data):
    cursor, limit = page_params(parse(data, PAGE), limits.PAGE_SIZE)
    query = InquiryThread.objects.select_related("business").filter(customer_account_id=ctx.actor_id).order_by("id")
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = list(query[:limit + 1])
    return Result(200, {"items": [customer_view(t, with_messages=False) for t in page[:limit]],
                        "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


@operation("inquiry_get_mine", roles=CUSTOMER, budget="read")
def inquiry_get_mine(ctx, data):
    fields = parse(data, {"thread_id": (uuid_text, True)})
    return Result(200, customer_view(_mine(ctx, fields["thread_id"])))


@operation("inquiry_message_customer", roles=CUSTOMER, verified_email=True, idempotent=True, budget="inquiry_message")
def inquiry_message_customer(ctx, data):
    fields = parse(data, {"thread_id": (uuid_text, True), "body": (_body, True)})
    with transaction.atomic():
        thread = _mine(ctx, fields["thread_id"], lock=True)
        if thread.state != T.OPEN:
            raise ApiError(409, "This conversation is closed", "thread_closed")
        _add_message(thread, "customer", ctx.actor_id, fields["body"])
    return Result(201, customer_view(thread))


@operation("inquiry_close_customer", roles=CUSTOMER, idempotent=True)
def inquiry_close_customer(ctx, data):
    fields = parse(data, {"thread_id": (uuid_text, True)})
    with transaction.atomic():
        thread = _mine(ctx, fields["thread_id"], lock=True)
        if thread.state != T.OPEN:
            raise ApiError(409, "This conversation is closed", "thread_closed")
        thread.state = T.CLOSED_BY_CUSTOMER
        thread.save(update_fields=["state"])
        security_audit.record("business.inquiry_closed", ctx.actor_id, "business", thread.business_id)
    return Result(200, customer_view(thread, with_messages=False))


def _confirm(thread, side, ctx):
    if thread.state == T.BLOCKED:
        raise not_found()
    sent = set(thread.messages.filter(removed=False).values_list("author_kind", flat=True))
    if sent != {"customer", "business"}:
        raise ApiError(409, "Both sides must have written before the conversation can be confirmed", "no_exchange")
    column = f"{side}_confirmed_at"
    if getattr(thread, column) is None:
        setattr(thread, column, timezone.now())
        thread.save(update_fields=[column])
        security_audit.record("business.inquiry_confirmed", ctx.actor_id, "business", thread.business_id)


@operation("inquiry_confirm_customer", roles=CUSTOMER, idempotent=True)
def inquiry_confirm_customer(ctx, data):
    fields = parse(data, {"thread_id": (uuid_text, True)})
    with transaction.atomic():
        thread = _mine(ctx, fields["thread_id"], lock=True)
        _confirm(thread, "customer", ctx)
    return Result(200, customer_view(thread, with_messages=False))


# ---- business ------------------------------------------------------------------------------------------------------
@operation("inquiry_inbox", roles=CUSTOMER, budget="read", member_roles=authz.ANY)
def inquiry_inbox(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), **PAGE})
    business_id = fields.pop("business_id")
    cursor, limit = page_params(fields, limits.PAGE_SIZE)
    business, _ = authz.require_member(ctx.actor_id, business_id)
    query = business.inquiry_threads.order_by("id")
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = list(query[:limit + 1])
    return Result(200, {"items": [business_view(t, with_messages=False) for t in page[:limit]],
                        "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


@operation("inquiry_inbox_get", roles=CUSTOMER, budget="read", member_roles=authz.ANY)
def inquiry_inbox_get(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "thread_id": (uuid_text, True)})
    return Result(200, business_view(_business_thread(ctx, fields["business_id"], fields["thread_id"])))


@operation("inquiry_reply", roles=CUSTOMER, idempotent=True, budget="inquiry_message", member_roles=authz.ANY)
def inquiry_reply(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "thread_id": (uuid_text, True), "body": (_body, True)})
    with transaction.atomic():
        thread = _business_thread(ctx, fields["business_id"], fields["thread_id"], lock=True)
        if thread.state != T.OPEN or thread.business.state == Business.State.CLOSED:
            raise ApiError(409, "This conversation is closed", "thread_closed")
        _add_message(thread, "business", ctx.actor_id, fields["body"])
    return Result(201, business_view(thread))


@operation("inquiry_close_business", roles=CUSTOMER, idempotent=True, member_roles=authz.ANY)
def inquiry_close_business(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "thread_id": (uuid_text, True)})
    with transaction.atomic():
        thread = _business_thread(ctx, fields["business_id"], fields["thread_id"], lock=True)
        if thread.state != T.OPEN:
            raise ApiError(409, "This conversation is closed", "thread_closed")
        thread.state = T.CLOSED_BY_BUSINESS
        thread.save(update_fields=["state"])
        security_audit.record("business.inquiry_closed", ctx.actor_id, "business", thread.business_id)
    return Result(200, business_view(thread, with_messages=False))


@operation("inquiry_confirm_business", roles=CUSTOMER, idempotent=True, member_roles=authz.ANY)
def inquiry_confirm_business(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "thread_id": (uuid_text, True)})
    with transaction.atomic():
        thread = _business_thread(ctx, fields["business_id"], fields["thread_id"], lock=True)
        _confirm(thread, "business", ctx)
    return Result(200, business_view(thread, with_messages=False))


@operation("inquiry_block", roles=CUSTOMER, idempotent=True, member_roles=(OWNER,))
def inquiry_block(ctx, data):
    """Owner blocks the thread's customer for this business. The customer is identified only through the thread."""
    fields = parse(data, {"business_id": (uuid_text, True), "thread_id": (uuid_text, True)})
    with transaction.atomic():
        thread = _business_thread(ctx, fields["business_id"], fields["thread_id"], (OWNER,), lock=True)
        InquiryBlock.objects.get_or_create(business=thread.business, customer_account_id=thread.customer_account_id,
                                           defaults={"blocked_by_account_id": ctx.actor_id})
        InquiryThread.objects.filter(business=thread.business, customer_account_id=thread.customer_account_id,
                                     state=T.OPEN).update(state=T.BLOCKED)
        thread.refresh_from_db()
        security_audit.record("business.inquiry_blocked", ctx.actor_id, "business", thread.business_id)
    return Result(200, business_view(thread, with_messages=False))
