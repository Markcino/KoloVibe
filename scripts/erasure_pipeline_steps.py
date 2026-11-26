"""Child-process steps for scripts/verify_erasure_pipeline_broker.py (Decision C slices 2a and 2b).

Usage: python scripts/erasure_pipeline_steps.py <identity|engagement|creators|moderation> <step> '<json arguments>'
Each step runs one service's real code against its own disposable PostgreSQL schema and prints one JSON line.
"""
import json
import sys
import uuid

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from event_pipeline_steps import setup  # noqa: E402


def _dispatch(dispatch_one, app, **options):
    errors, sent = [], 0
    for _ in range(50):
        try:
            if not dispatch_one(app, **options):
                break
            sent += 1
        except Exception as error:  # the outbox must keep the event; report the type only
            errors.append(type(error).__name__)
            break
    return {"sent": sent, "errors": errors}


def identity_approve(arguments):
    """An approved deletion as privacy_review applies it: deactivation, revoked sessions, one job and one event."""
    import secrets
    from django.db import transaction
    from service import erasure
    from service.models import Account, PrivacyRequest

    with transaction.atomic():
        person = Account.objects.create_user(f"person-{uuid.uuid4().hex[:8]}@example.test", secrets.token_urlsafe(24),
                                             "Person")
        item = PrivacyRequest.objects.create(account=person, kind="deletion")
        PrivacyRequest.objects.filter(pk=item.pk).update(status="processing")
        person.is_active = False
        person.save(update_fields=["is_active"])
        erasure.open_jobs(item)
    return {"request_id": str(item.id), "account_id": str(person.id)}


def identity_dispatch_real(arguments):
    from service import events
    from service.celery_app import app

    return _dispatch(events.dispatch_one, app)


def identity_state(arguments):
    from service.models import ErasureJob, PrivacyRequest, SecurityEvent

    jobs = ErasureJob.objects.filter(request_id=arguments["request_id"])
    return {"jobs": {job.service: {"confirmed": job.confirmed_at is not None, "counts": job.counts,
                                   "retained": job.retained} for job in jobs},
            "status": PrivacyRequest.objects.get(pk=arguments["request_id"]).status,
            "audit": SecurityEvent.objects.filter(kind="account.privacy_erasure_confirmed").count()}


def identity_worker(arguments):
    from staging_runtime import roles

    roles.run_celery("service.celery_app:app", "kolovibe.identity")
    return {}


def engagement_seed(arguments):
    from datetime import date, timedelta
    from django.utils import timezone
    from service.models import CreatorFollow, QualifiedWatch, VideoLike, VideoShare, WatchSession

    now, video, creator = timezone.now(), uuid.uuid4(), uuid.uuid4()
    for account in (arguments["account_id"], arguments["other_id"]):
        VideoLike.objects.create(video_id=video, account_id=account, creator_id=creator)
        CreatorFollow.objects.create(creator_id=creator, account_id=account)
        VideoShare.objects.create(account_id=account, video_id=video, creator_id=creator, day=date.today())
        WatchSession.objects.create(account_id=account, video_id=video, creator_user_id=creator, duration_ms=60000,
                                    revision=1, started_at=now, last_sample_at=now, expires_at=now + timedelta(hours=1))
    QualifiedWatch.objects.create(session_id=uuid.uuid4(), account_id=arguments["account_id"], video_id=video,
                                  creator_user_id=creator, qualified_at=now, duration_ms=60000)
    return {}


def engagement_dispatch_real(arguments):
    from service import events
    from service.celery_app import app

    return _dispatch(events.dispatch_one, app, privacy_only=True)


def engagement_state(arguments):
    from django.db import connection
    from service.models import CreatorFollow, QualifiedWatch, VideoLike, VideoShare, WatchSession

    def counts(account):
        return {model.__name__: model.objects.filter(account_id=account).count()
                for model in (VideoLike, CreatorFollow, VideoShare, WatchSession, QualifiedWatch)}

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM event_outbox WHERE event_type = 'privacy.erasure_confirmed' "
                       "AND published_at IS NULL")
        pending = cursor.fetchone()[0]
    return {"person": counts(arguments["account_id"]), "other": counts(arguments["other_id"]),
            "confirmations_pending": pending}


def engagement_worker(arguments):
    from staging_runtime import roles

    roles.run_celery("service.celery_app:app", "kolovibe.engagement")
    return {}


def _pending_confirmations():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM event_outbox WHERE event_type = 'privacy.erasure_confirmed' "
                       "AND published_at IS NULL")
        return cursor.fetchone()[0]


def creators_seed(arguments):
    from django.utils import timezone
    from service.models import CreatorApplication, CreatorProfile, OnboardingEvent

    for account in (arguments["account_id"], arguments["other_id"]):
        profile = CreatorProfile.objects.create(user_id=account, handle=f"c{uuid.uuid4().hex[:12]}",
                                                display_name="Creator", bio="Bio", status="active",
                                                reviewed_at=timezone.now())
        CreatorApplication.objects.create(account_id=account, invited_by=uuid.uuid4(), profile=profile,
                                          status="approved", attestation_version="v1")
        OnboardingEvent.objects.create(account_id=account, actor_id=uuid.uuid4(), action="approved")
    return {}


def creators_dispatch_real(arguments):
    from service import events
    from service.celery_app import app

    return _dispatch(events.dispatch_one, app)


def creators_state(arguments):
    from service.models import CreatorApplication, CreatorProfile, OnboardingEvent

    def counts(account):
        return {"profiles": CreatorProfile.objects.filter(user_id=account).count(),
                "applications": CreatorApplication.objects.filter(account_id=account).count(),
                "onboarding_events": OnboardingEvent.objects.filter(account_id=account).count()}

    return {"person": counts(arguments["account_id"]), "other": counts(arguments["other_id"]),
            "confirmations_pending": _pending_confirmations()}


def creators_worker(arguments):
    from staging_runtime import roles

    roles.run_celery("service.celery_app:app", "kolovibe.creators")
    return {}


def moderation_seed(arguments):
    from service.models import Report

    for account in (arguments["account_id"], arguments["other_id"]):
        Report.objects.create(id=uuid.uuid4(), video_id=uuid.uuid4(), reporter_id=account, reason="harm",
                              details="Free text the reporter wrote")
    return {}


def moderation_dispatch_real(arguments):
    from service import events
    from service.celery_app import app

    return _dispatch(events.dispatch_one, app)


def moderation_state(arguments):
    from service.models import Report

    def counts(account):
        return {"reports": Report.objects.filter(reporter_id=account).count()}

    return {"person": counts(arguments["account_id"]), "other": counts(arguments["other_id"]),
            "details_left": Report.objects.exclude(details="").count(),
            "confirmations_pending": _pending_confirmations()}


def moderation_worker(arguments):
    from staging_runtime import roles

    roles.run_celery("service.celery_app:app", "kolovibe.moderation")
    return {}


if __name__ == "__main__":
    service, step = sys.argv[1], sys.argv[2]
    setup(service)
    print("RESULT " + json.dumps(globals()[f"{service}_{step}"](json.loads(sys.argv[3]))))
