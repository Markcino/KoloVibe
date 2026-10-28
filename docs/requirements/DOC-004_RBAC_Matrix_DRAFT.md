> Source: DOC-004_RBAC_Matrix_DRAFT.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 2>
Role-Based Access Control Matrix
DOC-004 | Authorization model for MVP and future modules

Version 0.1 | 28 October 2026 | Status: Draft for stakeholder review. PRD and SRS v0.2 remain
approved baselines.



Authorization principles
   Deny by default; authenticate identity and verify resource ownership on Django server for
    every request.
   Roles are viewer, creator, moderator, support, finance, administrator and service worker. A user
    can hold multiple explicitly granted roles; no role inherits administrator rights implicitly.
   Scope all decisions to the resource, tenant/organization where applicable, operation, and
    current verification state.
   Privileged actions require MFA, separation of duties for financial operations, audit trail and
    least privilege.
   Mobile UI visibility is not an authorization control; enforce Django permissions and queryset
    filtering.

Operati     Anony      Viewer     Creator     Modera      Support    Finance     Admini      Worker
on          mous                              tor                    (later)     strator
Browse      Yes        Yes        Yes         Yes         Yes        Yes         Yes         System
approv
ed
public
videos
Edit        No         Own        Own         Own         Own        Own         Own         No
own
profile
Submit      No         Own        Own         No          No         No          No          No
creator
applicat
ion
Upload      No         No         Own,        No          No         No          No          Task-
media                             verified                                                   only
Edit/       No         No         Own         No          No         No          Policy-     Task-
delete                                                                           only        only
own
media
Like or     No         Yes        Yes         No          No         No          No          No
report
content
Read        No         No         Own         No          No         No          Audited     Task-
private                                                                          support     only
points                                                                           only
stateme
nt
Award/      No         No         No          No          No         No          Review      Rules
reverse                                                                          only        engine
points                                                                                       only
<PARSED TEXT FOR PAGE: 2 / 2>
Review     No          No         No         Assigne     Limited    No          Supervi    Task-
content                                      d           read                   se         only
reports
Remove     No          No         No         Assigne     No         No          Supervi    Policy-
/restore                                     d                                  se         only
reporte
d
content
Change     No          No         No         No          No         No          Restrict   No
roles                                                                           ed, MFA
View       No          No         No         Own         Limited    Finance     Authori    Write-
audit/se                                     actions     ticket     subset      zed,       only
curity                                                                          MFA
logs
Approv     No          No         No         No          No         Dual-       Cannot     No
e                                                                   control     self-
moneta                                                              later       approve
ry
payout



Implementation and verification
   Define Django custom user and RoleAssignment with explicit scope, validity and actor of grant.
   Use DRF permission classes plus object-level permission checks and scoped querysets.
   Use audit middleware and domain-level events for sensitive changes; never log tokens or
    unnecessary PII.
   Test each action as every role, including cross-user resource IDs, role revocation, disabled
    accounts and concurrency.
   Require two distinct approvers for future payout release; finance operations excluded from
    MVP.



Open decisions
   Whether viewers can browse anonymously or require accounts for all engagement.
   Whether creator verification is manual, automated or mixed; proof required.
   Moderator geographic/queue scope and support access policy.
   Retention and appeal policy for removed content.