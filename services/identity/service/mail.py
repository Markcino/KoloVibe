"""Verified STARTTLS SMTP; private CAs are explicit, never an insecure fallback."""

import os
import ssl

from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property


class VerifiedSMTPBackend(EmailBackend):
    @cached_property
    def ssl_context(self):
        context = ssl.create_default_context(cafile=os.environ.get("KOLOVIBE_SMTP_CA_FILE") or None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context
