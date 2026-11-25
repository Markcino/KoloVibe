# Owner decisions A to J (25 November 2026)

**Recorded from the owner's instruction "KOLOVIBE — Complete application reverification, development, security hardening and release acceptance", sent by Mark Gbalazeh (@Markcino), the accountable owner, on 25 November 2026 at 16:13 UTC.** It approves the ten decisions below for **development and staging testing**. It does not approve production activation, live money movement, live advertising, or the publication of legal text as legally approved.

This record resolves the open register entries named in the "Resolves" column. Where a decision approves a mechanism but supplies no values, the values remain open and are listed in section 2. Section 3 lists the points where the new decisions conflict with the standing principal engineering directive. Those points are put to the owner and are not decided here.

## 1. Decisions

| Decision | Summary | Resolves | Primary owner of the code |
| --- | --- | --- | --- |
| **A** Published content edits | An edit to a published video's title, description or tags creates a moderation-review revision. The approved version stays live, the creator is notified of the outcome, history and audit are kept, content can be restricted immediately, repeated edits cannot bypass review, and concurrent or duplicate edits are safe | RV2-01 (option b, with tags; category is not named, so it follows the same rule as a material field) | Content, Moderation |
| **B** Terms and privacy acceptance | Versioned legal documents with effective dates. Acceptance is mandatory at registration and validated on the backend, with history and re-acceptance. Policies are readable before registration. Marketing consent is separate and optional, and acknowledging the privacy notice is never consent to advertising or tracking. Draft legal text is marked pending legal review | RV2-02 (option b) | Identity, Flutter |
| **C** Privacy retention and deletion | Access, export, deletion, deactivation, step-up for sensitive requests, session revocation, deletion or anonymization, object-storage, search and cache cleanup, financial and legal exceptions, legal holds, backup expiry, request tracking, notifications, administrative review and audit. A configurable retention schedule per data category, with proposed (not invented) periods. A restored backup must not reactivate deleted accounts | ADR-020 mechanism (periods stay open), DR-BZ-18 mechanism, RV2-04 mechanism | Identity (orchestration), every service (its own data) |
| **D** Backup, restoration, logging and alerting | Encrypted backups, integrity checks, isolated restore tests, RTO and RPO, structured logs without secrets, centralized monitoring and alerts for hosts, broker, database, media, authentication abuse and finance | ADR-016 (backup and DR parts; managed versus self-hosted stays open), ADR-017 | Operations, every service |
| **E** Copyright management | In-app reports and claims by verified external rights holders, evidence, acknowledgement, human review, creator notice, restriction, dispute and appeal, reinstatement, repeat-infringer handling, fraud detection, confidential claimant data and audit. No automatic final judgments | D11-008 | Moderation, Content |
| **F** Creator restrictions | Warnings, upload, publishing and monetization restrictions, temporary and permanent suspension, appeals, expiry, reinstatement, human review, reason codes, policy versions and audit, all enforced by the backend. Financial effects distinguish future earnings, disputed earnings and already-earned amounts | D-8 | Creators, Moderation, Finance |
| **G** Centralized Identity step-up | One Identity mechanism: short-lived, purpose-bound, single-use proofs bound to the user, action, resource, audience, expiry and session, with rate limits, invalidation and audit | DR-BZ-33 (option A), DR-EV-05, DR-FIN-06, P6B-04 | Identity |
| **H** Events and ticketing | Approved scope expansion | DR-EV-01 (scope) | Events (new) |
| **I** Advertising and sponsorship | Approved scope expansion with two channels: Google advertising products, and direct campaigns bought by businesses and sponsors. Current Google policies must be verified before anything is chosen or activated | DR-AD-01 (scope) | Advertising (new) |
| **J** Finance and creator monetization | Finance owns the single authoritative monetary ledger. Points stays non-cash. Events and Advertising post financial transactions to Finance and keep no competing ledger. The creator pool is allocated in proportion to eligible points. Sandbox or simulation only | DR-FIN-01 (scope), **X-01** (one ledger in Finance; DR-EV-03 and DR-AD-03 are amended to post to Finance) | Finance (new), Points (snapshot) |

## 2. Values the decisions do not supply

These are configuration that must be approved before live activation. Until then the code ships with a documented **proposed** value or refuses to run.

| Item | Status | Where it is recorded |
| --- | --- | --- |
| Legal text (terms, privacy notice, copyright policy, creator enforcement policy) | Drafts are written and marked **pending qualified legal review** | Decisions B and E |
| Retention period for each data category, and legal-hold rules | Proposed with justification; **legal approval required** | Decision C, ADR-020, DR-BZ-18, RV2-04 |
| RTO and RPO targets, backup retention | Proposed; owner approval required | Decision D |
| Dead-letter values (RV2-03) | Proposed in Phase 2: retry ceiling 10 with backoff, dead letters kept 14 days with a bounded length, replay by an administrator only through the normal publish path. **Still to be confirmed by the infrastructure owner** | RV2-03 |
| Creator revenue-share percentage, payout threshold and schedule, eligibility rules, exchange rates, taxes | Configurable with no default; live activation refused until approved | Decision J |
| Google advertising products, account and settlement | Verified against current Google documentation before selection; no live ad units | Decision I |
| Business owner values already listed in the Business approval record (evidence checklist, categories, copy, review minimum) | Unchanged | `docs/architecture/business/BIZ-Owner_Approval_Record_2026-11-24.md` |

## 3. Conflicts with the standing directive (put to the owner)

The permanent principal engineering directive allows two apps only: Flutter for every non-privileged user, and a protected Django dashboard for administrators and moderators. It allows no public website or portal, and says points never become money.

| Item in the new instruction | Conflict | Interpretation used until the owner answers |
| --- | --- | --- |
| "Web-based copyright claim submission" by external rights holders | Needs a public web form, which the standing directive excludes | Build intake in Flutter for signed-in users and for verified external claimants. Publish a designated contact channel in the copyright policy draft. Build no public web form until the owner rules |
| Google advertising "appropriate to the mobile and web platforms" | The only web application is the privileged console, where ads would be inappropriate | Mobile only. No ads in the console |
| "Mobile and web policy screens" and "access to applicable policy documents before registration" | App stores require a public privacy-policy URL, which a no-public-website rule forbids | Policies in Flutter before registration and in the console. Hosting a public policy page needs an owner ruling |
| Advertiser dashboard and organizer tools | Must not be a web portal (DR-BZ-21 pattern) | Flutter, like Business owners |
| Creator allocation in proportion to points | Standing rule "points never become money" | Points stay non-cash and are never redeemed or converted. Finance uses a points snapshot only as the weighting of an approved revenue pool. The UI says points have no fixed monetary value |

## 4. Unchanged restrictions

Production remains NO-GO. No live payouts, real payments, live advertisements or production deployment. Staging deployment is allowed only when every gate in the instruction is met, and only to the authorized staging environment. Live streaming and a public website stay excluded unless the owner rules otherwise on section 3.
