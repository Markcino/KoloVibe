"""B4 — listings and discovery.

One eligibility predicate decides visibility (BZ-R-016); `refresh` makes the public projection match it inside the
same transaction as whatever changed. Public reads touch only `BusinessListing`. Policy as approved: only VERIFIED
businesses are discoverable (DR-BZ-05 A); anonymous callers read the minimal set; contacts go to signed-in
verified-email accounts under a daily reveal budget (DR-BZ-12); no distance search, no paid placement (DR-BZ-13).
"""
import base64
import datetime
import hashlib
import hmac
import json
import unicodedata

from django.conf import settings
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from . import authz, hours, limits, security_audit, throttle
from .api import Result, operation
from .errors import ApiError, not_found
from .models import Business, BusinessListing, ProfileRevision
from .validation import clean_text, parse, uuid_text

CUSTOMER = ("viewer", "creator")
EVERYONE = ("anonymous", "viewer", "creator", "moderator", "administrator")
OWNER = authz.OWNER


def eligibility(business):
    """Reasons a business cannot be listed (empty list = eligible). Codes only; none reveals private data."""
    reasons = []
    if business.state != Business.State.VERIFIED:
        reasons.append("not_verified")
    approved = business.revisions.filter(state=ProfileRevision.State.APPROVED).select_related("category").first()
    if approved is None or approved.category_id is None or not approved.county_code or not approved.city:
        reasons.append("no_approved_profile")
    return reasons, approved


def _summary(text):
    text = " ".join(text.split())
    return text if len(text) <= 200 else text[:197].rstrip() + "..."


def _hours_snapshot(business):
    return {"rules": [[r.weekday, r.opens_minute, r.closes_minute]
                      for r in business.hours_rules.order_by("weekday", "opens_minute")],
            "exceptions": [[e.on_date.isoformat(), e.closed, e.opens_minute, e.closes_minute]
                           for e in business.hours_exceptions.order_by("on_date")]}


def refresh(business):
    """Make the projection match the predicate. Call inside the transaction that changed any input."""
    business = Business.objects.get(pk=business.pk)
    reasons, approved = eligibility(business)
    if reasons or not business.owner_listed:
        BusinessListing.objects.filter(business=business).delete()
        return False
    contacts = [[c.kind, c.value] for c in approved.contacts.filter(is_public=True).order_by("kind", "value")]
    BusinessListing.objects.update_or_create(business=business, defaults={
        "display_name": approved.display_name, "name_sort": _normal(approved.display_name),
        "category_slug": approved.category.slug, "category_name": approved.category.name,
        "county_code": approved.county_code, "city": approved.city, "summary": _summary(approved.description),
        "description": approved.description, "address_line": approved.address_line if approved.address_public else "",
        "time_zone": approved.time_zone, "hours": _hours_snapshot(business), "contacts": contacts,
        "verified": business.state == Business.State.VERIFIED, "updated_at": timezone.now()})
    return True


def reconcile(*, apply=False):
    """Compare the projection with the predicate for every business; return drift counts and optionally repair."""
    drift = {"missing": 0, "stale": 0, "orphaned": 0}
    expected = set()
    for business in Business.objects.filter(owner_listed=True).iterator():
        reasons, _ = eligibility(business)
        if not reasons:
            expected.add(business.pk)
            if not BusinessListing.objects.filter(business=business).exists():
                drift["missing"] += 1
                if apply:
                    refresh(business)
    for listing in BusinessListing.objects.all().iterator():
        if listing.business_id not in expected:
            drift["orphaned"] += 1
            if apply:
                listing.delete()
    return drift


def _normal(name):
    return unicodedata.normalize("NFKD", name).casefold()[:80]


# ---- owner ---------------------------------------------------------------------------------------------------------
@operation("listing_status", roles=CUSTOMER, budget="read")
def listing_status(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    business, _ = authz.require_member(ctx.actor_id, fields["business_id"])
    reasons, _ = eligibility(business)
    return Result(200, {"listed": BusinessListing.objects.filter(business=business).exists(),
                        "owner_wants_listing": business.owner_listed, "eligible": not reasons, "reasons": reasons})


@operation("listing_publish", roles=CUSTOMER, idempotent=True, budget="listing_change")
def listing_publish(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        reasons, _ = eligibility(business)
        if reasons:
            raise ApiError(409, "The business is not eligible to be listed: " + ", ".join(reasons), "not_eligible")
        business.owner_listed = True
        business.save(update_fields=["owner_listed"])
        refresh(business)
        security_audit.record("business.listing_published", ctx.actor_id, "business", business.id)
    return Result(200, {"listed": True, "owner_wants_listing": True, "eligible": True, "reasons": []})


@operation("listing_unpublish", roles=CUSTOMER, idempotent=True, budget="listing_change")
def listing_unpublish(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    with transaction.atomic():
        business, _ = authz.require_member(ctx.actor_id, fields["business_id"], (OWNER,), lock=True)
        business = Business.objects.select_for_update().get(pk=business.pk)
        business.owner_listed = False
        business.save(update_fields=["owner_listed"])
        refresh(business)
        security_audit.record("business.listing_unpublished", ctx.actor_id, "business", business.id)
    reasons, _ = eligibility(business)
    return Result(200, {"listed": False, "owner_wants_listing": False, "eligible": not reasons, "reasons": reasons})


# ---- public ---------------------------------------------------------------------------------------------------------
def _public_budget(ctx):
    if not throttle.allow("public_read", ctx.throttle_key):
        raise ApiError(429, "Too many requests")


def _flag(value):
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ApiError(400, "Invalid request")


def _filters_digest(params):
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]


def _sign(payload):
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    mac = hmac.new(settings.SECRET_KEY.encode(), ("cursor:" + body).encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _unsign(cursor):
    try:
        body, mac = cursor.split(".")
        expected = hmac.new(settings.SECRET_KEY.encode(), ("cursor:" + body).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if not isinstance(payload, dict) or set(payload) != {"f", "t", "n", "i"}:
            raise ValueError
        return payload
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ApiError(400, "Invalid request") from None


def _item(listing, now):
    snapshot = listing.hours
    rules = [tuple(r) for r in snapshot.get("rules", [])]
    exceptions = [(datetime.date.fromisoformat(d), c, o, e) for d, c, o, e in snapshot.get("exceptions", [])]
    return {"id": str(listing.business_id), "display_name": listing.display_name,
            "category": {"slug": listing.category_slug, "name": listing.category_name},
            "county_code": listing.county_code, "city": listing.city, "summary": listing.summary,
            "verified": listing.verified, "open_now": hours.is_open(rules, exceptions, listing.time_zone, now)}


SEARCH_FIELDS = {"q": (lambda v: clean_text(v, 1, 100), False), "category": (lambda v: v, False),
                 "county": (lambda v: v, False), "city": (lambda v: clean_text(v, 1, 80), False),
                 "open_now": (_flag, False), "verified": (_flag, False), "sort": (lambda v: v, False),
                 "cursor": (lambda v: v, False), "limit": (lambda v: v, False)}


@operation("public_search", roles=EVERYONE)
def public_search(ctx, data):
    import re
    fields = parse(data, SEARCH_FIELDS)
    _public_budget(ctx)
    limit = fields.get("limit", limits.PAGE_SIZE)
    if isinstance(limit, str) and limit.isdigit() and len(limit) <= 3:
        limit = int(limit)
    if type(limit) is not int or not 1 <= limit <= limits.PAGE_SIZE:
        raise ApiError(400, "Invalid request")
    sort = fields.get("sort", "relevance" if "q" in fields else "name")
    if sort not in ("relevance", "name") or (sort == "relevance" and "q" not in fields):
        raise ApiError(400, "Invalid request")
    for name, pattern in (("category", r"[a-z0-9-]{2,60}"), ("county", r"[a-z0-9_]{2,40}")):
        if name in fields and (not isinstance(fields[name], str) or not re.fullmatch(pattern, fields[name])):
            raise ApiError(400, "Invalid request")
    if "cursor" in fields and (not isinstance(fields["cursor"], str) or len(fields["cursor"]) > 512):
        raise ApiError(400, "Invalid request")
    canonical = {k: v for k, v in fields.items() if k not in ("cursor", "limit")} | {"sort": sort}
    digest = _filters_digest(canonical)

    query = BusinessListing.objects.all()
    if "category" in fields:
        query = query.filter(category_slug=fields["category"])
    if "county" in fields:
        query = query.filter(county_code=fields["county"])
    if "city" in fields:
        query = query.filter(city__iexact=fields["city"])
    if "verified" in fields:
        query = query.filter(verified=fields["verified"])
    if "q" in fields:
        q = fields["q"]
        query = query.filter(Q(display_name__icontains=q) | Q(category_name__icontains=q) | Q(city__icontains=q)
                             | Q(description__icontains=q))
        tier = Case(When(display_name__icontains=q, then=Value(0)), default=Value(1), output_field=IntegerField())
    else:
        tier = Value(0, output_field=IntegerField())
    if sort == "name":  # alphabetical regardless of where the term matched
        tier = Value(0, output_field=IntegerField())
    query = query.annotate(tier=tier)
    ordering = ("tier", "name_sort", "business_id") if sort == "relevance" else ("name_sort", "business_id")

    position = None
    if "cursor" in fields:
        payload = _unsign(fields["cursor"])
        if payload["f"] != digest:
            raise ApiError(400, "Invalid request")
        position = (payload["t"], payload["n"], payload["i"])

    def after(pos):
        t, n, i = pos
        if sort == "name":
            return Q(name_sort__gt=n) | Q(name_sort=n, business_id__gt=i)
        return Q(tier__gt=t) | Q(tier=t, name_sort__gt=n) | Q(tier=t, name_sort=n, business_id__gt=i)

    def key(row):
        return (row.tier, row.name_sort, str(row.business_id))

    wanted_open = fields.get("open_now")
    now = timezone.now()
    results, scanned, exhausted = [], 0, False
    while len(results) <= limit and scanned < limits.SEARCH_SCAN_CAP:
        chunk_query = query.filter(after(position)) if position is not None else query
        chunk = list(chunk_query.order_by(*ordering)[:limits.SEARCH_CHUNK])
        if not chunk:
            exhausted = True
            break
        for row in chunk:
            scanned += 1
            position = key(row)
            item = _item(row, now)
            if wanted_open is not None and item["open_now"] is not wanted_open:
                continue
            results.append((key(row), item))
            if len(results) > limit:
                break
        if len(results) > limit:
            break
        if len(chunk) < limits.SEARCH_CHUNK:
            exhausted = True
            break
    page = results[:limit]
    if len(results) > limit:
        resume = page[-1][0]
    elif not exhausted:
        resume = position  # scan cap reached: continue after the last row examined
    else:
        resume = None
    next_cursor = _sign({"f": digest, "t": resume[0], "n": resume[1], "i": resume[2]}) if resume else None
    return Result(200, {"items": [item for _, item in page], "next_cursor": next_cursor})


@operation("public_detail", roles=EVERYONE)
def public_detail(ctx, data):
    fields = parse(data, {"business_id": (uuid_text, True)})
    _public_budget(ctx)
    listing = BusinessListing.objects.filter(business_id=fields["business_id"]).first()
    if listing is None:  # unknown, unlisted, suspended, revoked and closed look the same
        raise not_found()
    snapshot = listing.hours
    contacts, access = None, "sign_in_required"
    if not ctx.anonymous:
        if not ctx.email_verified:
            access = "verified_email_required"
        elif not listing.contacts:
            contacts, access = [], "none"
        elif throttle.allow("contact_reveal", ctx.actor_id):
            contacts, access = [{"kind": k, "value": v} for k, v in listing.contacts], "available"
        else:
            access = "limit_reached"
    item = _item(listing, timezone.now())
    from .reviews import rating_view
    return Result(200, {**item, "rating": rating_view(listing.business), "description": listing.description,
                        "address_line": listing.address_line or None, "time_zone": listing.time_zone,
                        "hours": {"rules": [{"weekday": w, "opens": hours.clock(o), "closes": hours.clock(c)}
                                            for w, o, c in snapshot.get("rules", [])],
                                  "exceptions": [{"on_date": d, "closed": cl, **({} if cl else {"opens": hours.clock(o), "closes": hours.clock(c)})}
                                                 for d, cl, o, c in snapshot.get("exceptions", [])]},
                        "contacts": contacts, "contacts_access": access})
