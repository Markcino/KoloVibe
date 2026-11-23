"""Reports, appeals, and reviewer moderation routes."""
from django.urls import path

from ..capabilities import enabled


def patterns():
    audit_routes = []
    if enabled("audit_read"):
        from ..admin_reads import audit_log
        audit_routes.append(path("api/v1/admin/audit", audit_log))
    if not enabled("moderation"):
        return audit_routes
    from ..moderation import moderation_endpoint
    from ..standing import standing
    from ..admin_reads import fraud_holds, moderation_assignments, moderation_assignment_summary

    routes = [
        path("api/v1/copyright/reports", moderation_endpoint, {"operation": "copyright_report"}),
        path("api/v1/videos/<uuid:target_id>/counter-notices", moderation_endpoint, {"operation": "counter_notice"}),
        path("api/v1/creators/me/copyright", moderation_endpoint, {"operation": "copyright_status"}),
        path("api/v1/moderation/totals", moderation_endpoint, {"operation": "totals"}),
        path("api/v1/engagement/fraud-holds", fraud_holds),
        path("api/v1/admin/moderation/assignments", moderation_assignments),
        path("api/v1/admin/moderation/assignments/summary", moderation_assignment_summary),
        path("api/v1/me/standing", standing, name="own-standing"),
        path("api/v1/creators/me/videos/<uuid:target_id>/notice", moderation_endpoint,
             {"operation": "notice"}, name="own-video-notice"),
        path("api/v1/reports", moderation_endpoint, {"operation": "report"}, name="submit-video-report"),
        path("api/v1/me/reports", moderation_endpoint, {"operation": "own_reports"}, name="own-reports"),
        path("api/v1/me/reports/<uuid:target_id>", moderation_endpoint,
             {"operation": "own_report"}, name="own-report-detail"),
        path("api/v1/me/appeals", moderation_endpoint, {"operation": "own_appeals"}, name="own-appeals"),
        path("api/v1/me/appeals/<uuid:target_id>", moderation_endpoint,
             {"operation": "own_appeal"}, name="own-appeal-detail"),
        path("api/v1/videos/<uuid:target_id>/appeals", moderation_endpoint,
             {"operation": "appeal"}, name="submit-video-appeal"),
        path("api/v1/moderation/videos", moderation_endpoint, {"operation": "review_queue"},
             name="review-video-queue"),
        path("api/v1/moderation/reports", moderation_endpoint, {"operation": "reports"},
             name="moderation-reports"),
        path("api/v1/moderation/appeals", moderation_endpoint, {"operation": "appeals"},
             name="moderation-appeals"),
        path("api/v1/moderation/videos/<uuid:target_id>/decisions", moderation_endpoint,
             {"operation": "video_decision"}, name="decide-video"),
        path("api/v1/moderation/reports/<uuid:target_id>/decisions", moderation_endpoint,
             {"operation": "report_decision"}, name="decide-video-report"),
        path("api/v1/moderation/appeals/<uuid:target_id>/decisions", moderation_endpoint,
             {"operation": "appeal_decision"}, name="decide-video-appeal"),
    ]

    for kind, operation in (("videos", "video_detail"), ("reports", "report_detail"), ("appeals", "appeal_detail")):
        routes.append(path(f"api/v1/moderation/{kind}/<uuid:target_id>", moderation_endpoint, {"operation": operation}))
    routes.append(path("api/v1/moderation/previews/<uuid:target_id>", moderation_endpoint, {"operation": "preview"}))
    return routes + audit_routes
