# KoloVibe policies page

The only public web pages the owner allowed ("Policies page only", 25 November 2026, widened on 26 November to add the account-deletion request page): a static site that serves the
current terms of service and privacy notice, as app store listings require. It has no accounts, feeds, ads, forms,
scripts, cookies or third-party resources.

The texts are not copied here. `scripts/build_policy_site.py` renders the exact files Identity serves
(`services/identity/service/legal_texts/`), so the page, the API and the app always show the same words and version.

    python scripts/build_policy_site.py build/policies

writes `index.html`, `terms/index.html`, `privacy/index.html`, `delete-account/index.html` and `policies.css`.

**Deletion request page** (owner ruling, 26 November 2026: "static policies page plus account-deletion page", and
nothing else public). Google Play requires a resource outside the app where people can ask for their account and data
to be deleted; it is declared in the Data safety form. The page is rendered from `delete-account.md` here. It has no
form: it describes the in-app request and an email route, whose address is still a placeholder for the owner to supply.
It is a draft pending legal review, like the other texts. The app links only `/terms`, `/privacy` and
`/delete-account` under `KOLOVIBE_PUBLIC_WEB_ORIGIN` (`PublicLinks.allowedPaths`), which match these paths. Every page carries the "pending legal review" banner
while the status is pending, and states the version and effective date.

**Not hosted.** Choosing where to serve it (and its domain, TLS and response headers) is an operations decision that
needs owner approval; nothing here deploys it. Serve it with at least:
`Content-Security-Policy: default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
`X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. The same policy is in each page's meta tag.
