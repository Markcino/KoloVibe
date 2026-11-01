# ADR-013 — Django-native client identity authority selection

**Record date:** 2026-11-01
**Decision owner:** KoloVibe product owner / sole developer
**Status:** **Partially decided — identity authority selected; token, sessions, privileged MFA and security acceptance pending**
**Related:** DOC-207 ADR-013, DOC-205 API contracts, DOC-206 security verification, DOC-209 G-03, Stage 3 OD-01 and FND-10

## Owner-confirmed selection

The owner explicitly selected **Django-native identity** for KoloVibe. The existing Django identity microservice, backed by PostgreSQL, is the intended authority for client account identities and authentication. Flutter and Django web clients use the existing API gateway and identity service boundaries; internal service authorization remains enforced separately.

**A managed identity provider (for example, an external OIDC provider) is not a required component of the present implementation.** Changing this identity authority in the future requires a separate reviewed architecture decision. This selection does not approve any new provider migration, code change, token type, secret, deployment or endpoint activation.

### Options recorded in DOC-207

- **Selected:** Django-native identity in the existing Django identity microservice. This aligns with the approved Django/DRF architecture, currently implemented account journeys and desire to avoid an additional managed identity dependency.
- **Not selected for the current implementation:** managed OIDC identity authority; a bespoke authentication system built from scratch. Keep these as historical alternatives, not active implementation dependencies.

## What has NOT yet been approved

The identity-provider decision alone is **not final ADR-013 approval**. Still open:

1. **Mobile credentials:** access-token format (opaque/JWT or alternative), issuer, audience, scope, access lifetime, secure device storage, refresh-token lifetime, rotation/reuse response, revocation and device/session management.
2. **Django web:** cookie/session model and lifetime, secure/HttpOnly/SameSite/CSRF settings, logout and revocation; reconcile browser and bearer credential boundaries.
3. **Privileged MFA:** factor(s), enrollment, step-up, recovery, administrative access and audited enforcement. The approved PRD requires MFA for privileged users; concrete factor and workflow remain to be accepted.
4. **Recovery and abuse prevention:** contact verification, password reset, account recovery, brute-force/rate limits, account enumeration resistance, compromised-credential handling and audit retention.
5. **Operational identity:** key generation, custody, rotation and revocation, trust boundaries, recovery exercises, real SMTP, environment secrets, and executable security tests.

**ADR-012 remains separate and open:** Django-native *client* identity does not decide inter-service mutual TLS, HMAC key ownership or workload credential issuer. Likewise, **Stage 3 OD-01 remains partially open** for the combined workload/end-user contract.

## Implementation and evidence boundaries

The repository already has local account registration/login, contact-verification fixtures, refresh rotation/revocation tests and secure web account journeys, as reported by the current Stage 3 tracker. The restricted staging deployment defaults account endpoints to disabled; it does not become approved simply because Django-native identity has been selected.

Before enabling external account registration/login or privileged routes, obtain the outstanding approvals and pass the DOC-205/DOC-206 checks for expired/replayed tokens, wrong audience, forged identity, privilege elevation, revocation, rate limits, MFA, recovery, and protected transport. Record the exact design and tested evidence in the main ADR register and Stage 3 tracker.

## Decision effect and change control

- Record the **owner's chosen identity authority** now in DOC-207 and dependent Stage 3 documentation.
- Keep **ADR-013 open for the remaining session/MFA requirements**. Do not mark it fully accepted, close DOC-209 G-03, or close Stage 3.
- Do not infer that using Django makes the application secure by default. Authentication and authorization still require OWASP ASVS/MASVS-aligned implementation and verification.
- This document records a **partial decision**, not a deployed service, completed security review, revised PRD, or unconditional architecture sign-off.
