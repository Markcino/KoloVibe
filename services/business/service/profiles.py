"""B3 — profiles: revisions, categories, contacts, location, hours and visibility flags.

The public sees only the last APPROVED revision. Material fields are pre-moderated; other edits apply on submit and
stay reportable (DR-BZ-11, approved). Images are not part of B3 (DR-BZ-20: no images until the shared pipeline exists).
"""
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import authz, hours, limits, listings, security_audit, step_up
from .api import Result, operation
from .errors import ApiError, not_found
from .models import (Business, BusinessCategory, ContactChannel, HoursException, HoursRule, ProfileRevision)
from .validation import PAGE, boolean, clean_text, code_text, page_params, parse, uuid_text

CUSTOMER, REVIEWERS = authz.CUSTOMER, authz.REVIEWERS
OWNER, STAFF = authz.OWNER, authz.STAFF
State = ProfileRevision.State
SLUG = re.compile(r"[a-z0-9-]{2,60}")
COUNTY = re.compile(r"[a-z0-9_]{2,40}")
PHONE = re.compile(r"\+?[0-9][0-9 ()\-]{5,24}")
SCALARS = ("display_name", "category", "description", "county_code", "city", "address_line", "address_public",
           "latitude", "longitude", "coordinates_public", "time_zone")


def _slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise ApiError(400, "Invalid request")
    return value


def _county(value):
    if not isinstance(value, str) or not COUNTY.fullmatch(value):
        raise ApiError(400, "Invalid request")
    return value


def _coordinate(low, high):
    def check(value):
        if value is None:
            return None
        if type(value) not in (int, float, str):
            raise ApiError(400, "Invalid request")
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ApiError(400, "Invalid request") from None
        if not number.is_finite() or not Decimal(low) <= number <= Decimal(high):
            raise ApiError(400, "Invalid request")
        return number.quantize(Decimal("0.000001"))
    return check


def _contact_value(kind, value):
    value = clean_text(value, 3, 300)
    if kind == "phone":
        if not PHONE.fullmatch(value) or not 7 <= sum(c.isdigit() for c in value) <= 15:
            raise ApiError(400, "Invalid request")
    elif kind == "email":
        try:
            validate_email(value)
        except ValidationError:
            raise ApiError(400, "Invalid request") from None
        if len(value) > 254:
            raise ApiError(400, "Invalid request")
        value = value.casefold()
    else:  # website and social links: https only, a host, no credentials
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or " " in value:
            raise ApiError(400, "Invalid request")
    return value


def _contacts(value):
    if not isinstance(value, list) or len(value) > limits.MAX_CONTACTS:
        raise ApiError(400, "Invalid request")
    out, seen = [], set()
    for item in value:
        row = parse(item, {"kind": (lambda v: v, True), "value": (lambda v: v, True), "is_public": (boolean, False)})
        if row["kind"] not in ContactChannel.Kind.values:
            raise ApiError(400, "Invalid request")
        row["value"] = _contact_value(row["kind"], row["value"])
        if (row["kind"], row["value"]) in seen:
            raise ApiError(400, "Invalid request")
        seen.add((row["kind"], row["value"]))
        out.append((row["kind"], row["value"], row.get("is_public", False)))
    return out


EDIT_FIELDS = {
    "business_id": (uuid_text, True),
    "display_name": (lambda v: clean_text(v, 2, 80), False),
    "category": (_slug, False),
    "description": (lambda v: clean_text(v, 0, 2000, multiline=True), False),
    "county_code": (_county, False),
    "city": (lambda v: clean_text(v, 1, 80), False),
    "address_line": (lambda v: clean_text(v, 0, 200), False),
    "address_public": (boolean, False),
    "latitude": (_coordinate("-90", "90"), False),
    "longitude": (_coordinate("-180", "180"), False),
    "coordinates_public": (boolean, False),
    "time_zone": (hours.time_zone, False),
    "contacts": (_contacts, False),
}


def _contact_set(revision):
    return {(c.kind, c.value, c.is_public) for c in revision.contacts.all()}


def _snapshot(revision):
    return {"display_name": revision.display_name, "category": revision.category_id, "description": revision.description,
            "county_code": revision.county_code, "city": revision.city, "address_line": revision.address_line,
            "address_public": revision.address_public, "latitude": revision.latitude, "longitude": revision.longitude,
            "coordinates_public": revision.coordinates_public, "time_zone": revision.time_zone,
            "contacts": _contact_set(revision)}


def changed_fields(revision, baseline):
    now = _snapshot(revision)
    before = _snapshot(baseline) if baseline is not None else {key: None for key in now}
    return sorted(key for key in now if now[key] != before[key])


def _approved(business):
    return business.revisions.filter(state=State.APPROVED).first()


def _revision_view(revision, *, with_changes=None):
    data = {"id": str(revision.id), "revision_no": revision.revision_no, "state": revision.state,
            "display_name": revision.display_name,
            "category": revision.category.slug if revision.category_id else None,
            "description": revision.description, "county_code": revision.county_code, "city": revision.city,
            "address_line": revision.address_line, "address_public": revision.address_public,
            "latitude": str(revision.latitude) if revision.latitude is not None else None,
            "longitude": str(revision.longitude) if revision.longitude is not None else None,
            "coordinates_public": revision.coordinates_public, "time_zone": revision.time_zone,
            "contacts": [{"kind": c.kind, "value": c.value, "is_public": c.is_public}
                         for c in revision.contacts.order_by("kind", "value")],
            "reason_code": revision.reason_code or None}
    if with_changes is not None:
        data["changed_fields"] = with_changes
    return data


def _hours_view(business):
    rules = business.hours_rules.order_by("weekday", "opens_minute")
    exceptions = business.hours_exceptions.order_by("on_date")
    return {"rules": [{"weekday": r.weekday, "opens": hours.clock(r.opens_minute), "closes": hours.clock(r.closes_minute)}
                      for r in rules],
            "exceptions": [{"on_date": e.on_date.isoformat(), "closed": e.closed,
                            **({} if e.closed else {"opens": hours.clock(e.opens_minute),
                                                    "closes": hours.clock(e.closes_minute)})} for e in exceptions]}


def _open(business):
    return business.state != Business.State.CLOSED


@operation("profile_get", roles=CUSTOMER, budget="read", member_roles=authz.ANY)
def profile_get(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    business, _ = authz.require_member(ctx.actor_id, fields["business_id"])
    working = business.revisions.filter(state__in=(State.DRAFT, State.PENDING_REVIEW)).first()
    latest_rejected = (business.revisions.filter(state=State.REJECTED).order_by("-revision_no").first()
                       if working is None else None)
    approved = _approved(business)
    return Result(200, {
        "approved": _revision_view(approved) if approved else None,
        "working": _revision_view(working, with_changes=changed_fields(working, approved)) if working else None,
        "last_rejected": _revision_view(latest_rejected) if latest_rejected else None,
        "hours": _hours_view(business)})


@operation("profile_edit", roles=CUSTOMER, idempotent=True, budget="profile_edit", member_roles=(OWNER,))
def profile_edit(ctx, data):
    fields = parse(data, EDIT_FIELDS)
    business_id = fields.pop("business_id")
    if not fields:
        raise ApiError(400, "Invalid request")
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, business_id, (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        if not _open(business):
            raise ApiError(409, "Business is closed", "business_closed")
        approved = _approved(business)
        working = business.revisions.select_for_update().filter(state__in=(State.DRAFT, State.PENDING_REVIEW)).first()
        if working is not None and working.state == State.PENDING_REVIEW:
            raise ApiError(409, "A revision is awaiting review", "revision_pending")
        if working is None:
            number = (business.revisions.aggregate(top=Max("revision_no"))["top"] or 0) + 1
            if approved is not None:
                base = _snapshot(approved)
                working = ProfileRevision.objects.create(
                    business=business, revision_no=number, display_name=base["display_name"],
                    category_id=base["category"], description=base["description"], county_code=base["county_code"],
                    city=base["city"], address_line=base["address_line"], address_public=base["address_public"],
                    latitude=base["latitude"], longitude=base["longitude"],
                    coordinates_public=base["coordinates_public"], time_zone=base["time_zone"])
                for kind, value, public in base["contacts"]:
                    ContactChannel.objects.create(revision=working, kind=kind, value=value, is_public=public)
            else:
                working = ProfileRevision.objects.create(business=business, revision_no=number,
                                                         display_name=business.display_name)
        contacts = fields.pop("contacts", None)
        if "category" in fields:
            category = BusinessCategory.objects.filter(slug=fields.pop("category"), active=True).first()
            if category is None:
                raise ApiError(400, "Unknown category", "unknown_category")
            working.category = category
        for name, value in fields.items():
            setattr(working, name, value)
        if (working.latitude is None) != (working.longitude is None):
            raise ApiError(400, "Latitude and longitude are set together")
        working.save()
        if contacts is not None:
            if approved is not None and set(contacts) != _contact_set(approved):
                step_up.require(ctx.actor_id, "business.contact_change")  # a live contact detail is being changed
            working.contacts.all().delete()
            ContactChannel.objects.bulk_create([ContactChannel(revision=working, kind=k, value=v, is_public=p)
                                                for k, v, p in contacts])
        security_audit.record("business.profile_edited", ctx.actor_id, "business", business.id)
    return Result(200, _revision_view(working, with_changes=changed_fields(working, approved)))


@operation("profile_submit", roles=CUSTOMER, idempotent=True, budget="profile_edit", member_roles=(OWNER,))
def profile_submit(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        if not _open(business):
            raise ApiError(409, "Business is closed", "business_closed")
        working = business.revisions.select_for_update().filter(state=State.DRAFT).first()
        if working is None:
            raise ApiError(409, "There is no draft revision to submit", "no_draft")
        approved = _approved(business)
        changes = changed_fields(working, approved)
        if not changes:
            raise ApiError(409, "Nothing has changed", "no_changes")
        missing = [name for name, ok in (("category", working.category_id), ("county_code", working.county_code),
                                         ("city", working.city)) if not ok]
        if missing:
            raise ApiError(409, "The profile is incomplete: " + ", ".join(missing), "incomplete_profile")
        now = timezone.now()
        working.submitted_at, working.submitted_by_account_id = now, ctx.actor_id
        material = approved is None or bool(set(changes) & set(limits.MATERIAL_FIELDS))
        if material:
            working.state = State.PENDING_REVIEW
            working.save(update_fields=["state", "submitted_at", "submitted_by_account_id"])
            security_audit.record("business.profile_submitted", ctx.actor_id, "business", business.id)
        else:  # free-text changes apply now and stay reportable
            _approve(business, working, ctx.actor_id, now, "applied_without_review")
            security_audit.record("business.profile_applied", ctx.actor_id, "business", business.id)
    view = _revision_view(working)
    view["applied"] = not material
    return Result(200, view)


def _approve(business, revision, reviewer_id, now, reason_code):
    ProfileRevision.objects.filter(business=business, state=State.APPROVED).update(state=State.SUPERSEDED)
    revision.state, revision.reviewed_by_account_id, revision.reviewed_at = State.APPROVED, reviewer_id, now
    revision.reason_code = reason_code
    revision.save(update_fields=["state", "reviewed_by_account_id", "reviewed_at", "reason_code", "submitted_at",
                                 "submitted_by_account_id"])
    if business.display_name != revision.display_name:
        business.display_name = revision.display_name
        business.save(update_fields=["display_name"])
    listings.refresh(business)


@operation("hours_replace", roles=CUSTOMER, idempotent=True, budget="profile_edit", member_roles=authz.ANY)
def hours_replace(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True), "rules": (lambda v: v, True),
                          "exceptions": (lambda v: v, False)})
    business_id = fields.pop("business_id")
    rules, exceptions = hours.validate(fields)
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, business_id, (OWNER, STAFF), lock=True)
        if not _open(business):
            raise ApiError(409, "Business is closed", "business_closed")
        business.hours_rules.all().delete()
        business.hours_exceptions.all().delete()
        HoursRule.objects.bulk_create([HoursRule(business=business, weekday=d, opens_minute=o, closes_minute=c)
                                       for d, o, c in rules])
        HoursException.objects.bulk_create([HoursException(business=business, on_date=d, closed=cl, opens_minute=o,
                                                           closes_minute=c) for d, cl, o, c in exceptions])
        listings.refresh(business)
        security_audit.record("business.hours_replaced", ctx.actor_id, "business", business.id)
    return Result(200, _hours_view(business))


# ---- categories ----------------------------------------------------------------------------------------------------
def _category_view(category):
    return {"slug": category.slug, "name": category.name, "active": category.active,
            "parent": category.parent.slug if category.parent_id else None}


@operation("category_list", roles=authz.EVERYONE)
def category_list(ctx, data):
    parse(data, {})
    items = BusinessCategory.objects.select_related("parent").filter(active=True).order_by("slug")
    return Result(200, {"items": [_category_view(c) for c in items]})


@operation("category_put", roles=("administrator",), mfa=True, idempotent=True)
def category_put(ctx, data):
    fields = parse(data, {"slug": (_slug, True), "name": (lambda v: clean_text(v, 2, 80), True),
                          "parent": (lambda v: None if v is None else _slug(v), False), "active": (boolean, True)})
    with transaction.atomic():
        parent = None
        if fields.get("parent"):
            parent = BusinessCategory.objects.filter(slug=fields["parent"]).first()
            if parent is None:
                raise ApiError(400, "Unknown parent", "unknown_parent")
            if parent.parent_id is not None or parent.slug == fields["slug"]:
                raise ApiError(409, "Categories have at most two levels", "depth_exceeded")
        category, created = BusinessCategory.objects.select_for_update().get_or_create(
            slug=fields["slug"], defaults={"name": fields["name"], "parent": parent, "active": fields["active"]})
        if not created:
            if category.children.exists() and parent is not None:
                raise ApiError(409, "Categories have at most two levels", "depth_exceeded")
            category.name, category.parent, category.active = fields["name"], parent, fields["active"]
            category.save(update_fields=["name", "parent", "active"])
        security_audit.record("business.category_changed", ctx.actor_id, "account", ctx.actor_id)
    return Result(200, _category_view(category))


# ---- reviewers ------------------------------------------------------------------------------------------------------
def _revision_for_reviewer(ctx, revision_id, *, lock=False):
    query = ProfileRevision.objects.select_related("business", "category").filter(pk=revision_id)
    if lock:
        query = query.select_for_update(of=("self",))
    revision = query.first()
    if (revision is None or revision.state != State.PENDING_REVIEW
            or not authz.has_grant(ctx.actor_id, "profile_review", revision.business_id)
            or revision.submitted_by_account_id == ctx.actor_id or authz.is_affiliated(ctx.actor_id, revision.business)):
        raise not_found()
    return revision


@operation("profile_queue", roles=REVIEWERS, mfa=True, budget="read")
def profile_queue(ctx, data):
    cursor, limit = page_params(parse(data, PAGE),
                                limits.PAGE_SIZE)
    everything, targets = authz.granted_targets(ctx.actor_id, "profile_review")
    query = ProfileRevision.objects.select_related("business").filter(state=State.PENDING_REVIEW).order_by("id")
    if not everything:
        query = query.filter(business_id__in=targets)
    if cursor is not None:
        query = query.filter(id__gt=cursor)
    page = [r for r in query[:limit + 1]]
    with transaction.atomic():
        security_audit.record("business.profile_queue_read", ctx.actor_id, "account", ctx.actor_id)
    visible = [r for r in page[:limit] if r.submitted_by_account_id != ctx.actor_id
               and not authz.is_affiliated(ctx.actor_id, r.business)]
    return Result(200, {"items": [{"revision_id": str(r.id), "business_id": str(r.business_id),
                                   "display_name": r.display_name, "submitted_at": r.submitted_at.isoformat()}
                                  for r in visible],
                        "next_cursor": str(page[limit - 1].id) if len(page) > limit else None})


@operation("profile_revision", roles=REVIEWERS, mfa=True, budget="read")
def profile_revision(ctx, data):
    fields = parse(data, {"revision_id": (uuid_text, True)})
    revision = _revision_for_reviewer(ctx, fields["revision_id"])
    with transaction.atomic():
        security_audit.record("business.profile_revision_read", ctx.actor_id, "business", revision.business_id)
    changes = changed_fields(revision, _approved(revision.business))
    return Result(200, {"business_id": str(revision.business_id), **_revision_view(revision, with_changes=changes)})


@operation("profile_decide", roles=REVIEWERS, mfa=True, idempotent=True)
def profile_decide(ctx, data):
    fields = parse(data, {"revision_id": (uuid_text, True), "decision": (lambda v: v, True), "reason_code": (code_text, True)})
    if fields["decision"] not in ("approve", "reject"):
        raise ApiError(400, "Invalid request")
    now = timezone.now()
    with transaction.atomic():
        revision = _revision_for_reviewer(ctx, fields["revision_id"], lock=True)
        business = Business.objects.select_for_update().get(pk=revision.business_id)
        if fields["decision"] == "approve":
            _approve(business, revision, ctx.actor_id, now, fields["reason_code"])
        else:
            revision.state, revision.reviewed_by_account_id = State.REJECTED, ctx.actor_id
            revision.reviewed_at, revision.reason_code = now, fields["reason_code"]
            revision.save(update_fields=["state", "reviewed_by_account_id", "reviewed_at", "reason_code"])
        security_audit.record("business.profile_decided", ctx.actor_id, "business", business.id)
    return Result(200, {"revision_id": str(revision.id), "state": revision.state})
