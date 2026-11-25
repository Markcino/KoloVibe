# KoloVibe policies page

The one public web page the owner allowed ("Policies page only", 25 November 2026): a static site that serves the
current terms of service and privacy notice, as app store listings require. It has no accounts, feeds, ads, forms,
scripts, cookies or third-party resources.

The texts are not copied here. `scripts/build_policy_site.py` renders the exact files Identity serves
(`services/identity/service/legal_texts/`), so the page, the API and the app always show the same words and version.

    python scripts/build_policy_site.py build/policies

writes `index.html`, `terms/index.html`, `privacy/index.html` and `policies.css`. The paths match the app's
`/terms` and `/privacy` links (`KOLOVIBE_PUBLIC_WEB_ORIGIN`). Every page carries the "pending legal review" banner
while the status is pending, and states the version and effective date.

**Not hosted.** Choosing where to serve it (and its domain, TLS and response headers) is an operations decision that
needs owner approval; nothing here deploys it. Serve it with at least:
`Content-Security-Policy: default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
`X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. The same policy is in each page's meta tag.
