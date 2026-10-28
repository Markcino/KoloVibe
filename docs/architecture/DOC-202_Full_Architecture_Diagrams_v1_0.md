# DOC-202 — Complete Architecture and Data-Flow Diagrams
Version 1.0 · FULL REVIEW DRAFT · 28 October 2026

**Baseline:** Approved DOC-201 v1.0. Microservices deployed in Docker Swarm. Nginx on a separate server/VM outside Swarm (DEC-004). No production deployment or validation is claimed.

## Diagram register

### DFD-01: System context and external trust boundaries

```mermaid
flowchart LR
  mobile[Flutter mobile clients] -->|HTTPS| cf[Cloudflare edge / WAF]
  browser[Web browsers] -->|HTTPS| cf
  cf -->|Authenticated origin TLS| nginx[Dedicated Nginx VM OUTSIDE Swarm]
  nginx -->|Private TLS upstream| ingress[Swarm published gateway endpoint]
  ingress --> web[Django web frontend]
  ingress --> api[API gateway / BFF]
  api --> auth[Identity service]
  api --> content[Content service]
  api --> engagement[Engagement service]
  api --> moderation[Moderation service]
  engagement --> points[Points ledger service]
  content --> stream[Cloudflare Stream / video provider]
  ads[Ad platforms] -.->|Separate reporting; no ad-based points| reporting[Reporting / reconciliation]
  classDef trust fill:#e8f1fc,stroke:#1d4f91
  class nginx,ingress trust
```

**Design notes:** External requests enter via Cloudflare, then the dedicated Nginx VM. Only approved public routes are forwarded into the Swarm cluster. Provider webhooks require signature validation and replay protection.

### DFD-02: Physical deployment and network zones

```mermaid
flowchart TB
  internet((Internet)) --> edge[Cloudflare edge]
  subgraph dmz[DMZ / reverse proxy zone]
    nginx[Dedicated Nginx VM: 443 public; 22 restricted]
  end
  edge -->|443 TLS; authenticated origin| nginx
  subgraph private[Private application network]
    vip[Swarm gateway VIP: private 8443 or 443]
    subgraph swarm[Docker Swarm cluster]
      m1[Manager 1]
      m2[Manager 2 - HA option]
      m3[Manager 3 - HA option]
      w1[Worker 1]
      w2[Worker 2 - HA option]
      services[Replicated app services]
      m1 --- services
      w1 --- services
    end
    vip --> services
    subgraph data[Restricted data zone]
      pg[(PostgreSQL)]
      redis[(Redis / broker)]
      backup[(Encrypted backup target)]
    end
    services --> pg
    services --> redis
    pg --> backup
  end
  nginx -->|Private VPN / allowlisted TLS upstream| vip
  admin[Admin via VPN / bastion] -.-> nginx
  admin -.-> m1
  admin -.-> pg
```

**Design notes:** Node counts are deployment options, not confirmed inventory. Three managers are recommended for manager quorum in production HA. Never expose PostgreSQL, Redis, or Docker daemon publicly.

### DFD-03: Service ownership and communications

```mermaid
flowchart LR
  gateway[API gateway / BFF] --> identity[Identity]
  gateway --> profiles[Profiles]
  gateway --> content[Content]
  gateway --> moderation[Moderation]
  gateway --> engagement[Engagement]
  gateway --> points[Points read API]
  content -->|outbox event| broker[(Broker)]
  engagement -->|verified event; idempotency key| broker
  broker --> points[Points ledger]
  broker --> moderation
  identity --> db1[(Identity schema / DB)]
  profiles --> db2[(Profile schema / DB)]
  content --> db3[(Content schema / DB)]
  engagement --> db4[(Engagement schema / DB)]
  points --> db5[(Points schema / DB)]
  moderation --> db6[(Moderation schema / DB)]
  note[No cross-service direct table writes] -.-> db1
```

**Design notes:** Logical ownership is per service. A shared physical PostgreSQL instance may be used initially with separate databases or schemas, separate credentials and no cross-service write access.

### DFD-04: Identity, authorization and service trust

```mermaid
sequenceDiagram
  participant C as Flutter / Browser
  participant N as Dedicated Nginx
  participant G as Gateway
  participant I as Identity
  participant S as Resource service
  C->>N: HTTPS login / request
  N->>G: TLS upstream + sanitized proxy headers
  G->>I: Login / session validation
  I-->>G: Short-lived signed identity assertion
  G->>S: Authenticated request + correlation ID
  S->>S: Verify token, audience, scopes, object ownership
  S-->>G: Authorized response
  G-->>C: Result
  Note over G,S: Network location alone never grants authorization
```

**Design notes:** Browser sessions should use secure HttpOnly cookies and CSRF protection; mobile access may use short-lived tokens and secure refresh-token rotation. Final identity protocol and key management require DOC-205/207 decisions.

### DFD-05: Video upload, processing and publication

```mermaid
sequenceDiagram
  participant C as Creator client
  participant A as Content API
  participant P as Video provider
  participant W as Provider webhook receiver
  participant M as Moderation
  C->>A: Create upload intent (auth, limits)
  A->>P: Create short-lived upload authorization
  P-->>A: Restricted upload token / URL
  A-->>C: Upload authorization
  C->>P: Upload video directly
  P->>W: Signed processing callback
  W->>W: Verify signature, timestamp, replay, asset mapping
  W->>A: Mark asset processed (idempotent)
  A->>M: Submit for moderation
  M-->>A: Approve or reject
  A-->>C: Publish only after approved state
```

**Design notes:** Untrusted uploads never become publicly discoverable until processing, ownership verification, and moderation checks pass. Avoid sending raw video through Nginx/Django unless a fallback is explicitly designed.

### DFD-06: Playback authorization and telemetry

```mermaid
sequenceDiagram
  participant V as Viewer
  participant A as Content API
  participant P as Stream provider
  participant E as Engagement API
  V->>A: Request video
  A->>A: Check visibility, bans, age policy
  A-->>V: Playback token / manifest authorization
  V->>P: Fetch segments with authorized playback
  V->>E: Signed session telemetry, bounded intervals
  E->>E: Rate-limit; deduplicate; assess genuine activity
  E-->>V: Acknowledge event (not a points promise)
```

**Design notes:** Client telemetry is untrusted. Playback authorization, eligibility windows, device/session abuse signals, and independent server checks are required; exact qualified-view thresholds remain an open business decision.

### DFD-07: Qualified engagement and non-cash points ledger

```mermaid
sequenceDiagram
  participant C as Client
  participant E as Engagement service
  participant DB as Engagement DB
  participant B as Durable event broker
  participant L as Points ledger service
  participant LD as Points DB
  C->>E: View / like event with session context
  E->>E: Validate account, rate, time, fraud signals
  E->>DB: Persist event + decision + outbox atomically
  DB-->>B: Publish verified engagement via outbox relay
  B->>L: Verified event + unique idempotency key
  L->>LD: Insert immutable non-cash ledger entry once
  L-->>B: Ack only after durable commit
  Note over E,L: Ad views/clicks NEVER create reward events
  Note over L,LD: Reversal is compensating entry; no destructive edit
```

**Design notes:** Ledger rules must remain server-owned, auditable and replay-safe. Pending points formulas and qualification criteria must be resolved before enabling awards. No payout functionality in Release 1.

### DFD-08: Moderation and appeal lifecycle

```mermaid
stateDiagram-v2
  [*] --> UploadPending
  UploadPending --> Processing
  Processing --> ReviewPending
  Processing --> Failed
  ReviewPending --> Published: Approved
  ReviewPending --> Rejected: Violates policy
  Published --> Restricted: Report / automated flag
  Restricted --> Published: Review clears
  Restricted --> Removed: Confirmed violation
  Rejected --> AppealPending: Eligible appeal
  Removed --> AppealPending: Eligible appeal
  AppealPending --> Published: Reinstated
  AppealPending --> Removed: Upheld
  Failed --> [*]
```

**Design notes:** Moderation decisions require role checks, reason codes, timestamps and audit trails. Content availability and engagement eligibility must react consistently to takedowns and reversals.

### DFD-09: Asynchronous reliability and recovery

```mermaid
flowchart TD
  req[API command] --> txn[Commit domain change + outbox in same DB transaction]
  txn --> relay[Outbox relay]
  relay --> broker[(Durable broker)]
  broker --> worker[Consumer]
  worker --> idem{Idempotency key processed?}
  idem -->|Yes| ack[Acknowledge duplicate]
  idem -->|No| action[Transactional business action]
  action --> ok{Success?}
  ok -->|Yes| ack
  ok -->|Transient error| retry[Bounded exponential retry]
  retry --> broker
  ok -->|Permanent failure| dlq[Dead-letter queue + alert]
  dlq --> manual[Authorized review / replay]
```

**Design notes:** This is an at-least-once delivery model with idempotent consumers, not exactly-once delivery. Retries and dead-letter processing require monitoring and access control.

### DFD-10: Swarm rollout and rollback

```mermaid
flowchart LR
  dev[Reviewed merge] --> ci[CI: tests + SAST + dependencies]
  ci --> build[Build immutable image + SBOM]
  build --> sign[Sign / attest image]
  sign --> reg[Private registry]
  reg --> gate[Manual production approval]
  gate --> deploy[Swarm stack deploy with pinned digest]
  deploy --> check[Health/readiness + smoke tests]
  check --> pass{Healthy?}
  pass -->|Yes| observe[Monitor errors and latency]
  pass -->|No| rollback[Rollback to prior image digest]
  rollback --> incident[Incident record]
  observe --> incident
```

**Design notes:** Schema changes must be backward-compatible across rolling updates. Database rollback is not assumed; use expand/migrate/contract and tested recovery procedures.

### DFD-11: Security trust zones and permitted flows

```mermaid
flowchart LR
  public[Public clients - untrusted] -->|443| cf[Cloudflare]
  cf -->|443 origin TLS| ng[Dedicated Nginx VM]
  ng -->|Private TLS 443/8443| gw[Swarm gateway]
  gw -->|Overlay; authenticated APIs| svc[Application services]
  svc -->|5432 restricted| pg[(PostgreSQL)]
  svc -->|6379 restricted| r[(Redis)]
  mgr[Swarm managers] <-->|2377 TCP, 7946 TCP/UDP, 4789 UDP - internal only| nodes[Swarm nodes]
  ops[Ops VPN / bastion] -.->|SSH restricted| ng
  ops -.->|SSH restricted| mgr
  classDef critical fill:#fff2f0,stroke:#ad3131
  class pg,r,mgr critical
```

**Design notes:** Port numbers are reference defaults and must be validated against actual Swarm overlay encryption, private networking and chosen reverse-proxy implementation. Docker published ports may bypass host firewall assumptions; test actual rules.

### DFD-12: Audit, metrics and operational telemetry

```mermaid
flowchart LR
  nginx[Nginx VM] --> logs[Central logs]
  services[Swarm services] --> logs
  services --> metrics[Metrics / traces]
  workers[Workers] --> metrics
  pg[PostgreSQL] --> metrics
  logs --> siem[Security alerts / audit review]
  metrics --> alerts[On-call alerting]
  alerts --> runbooks[Incident runbooks]
  siem --> runbooks
  backups[Backup jobs] --> restore[Tested restore exercises]
  restore --> runbooks
```

**Design notes:** Correlate requests across services using non-sensitive trace IDs. Mask tokens and personal information. Audit trails require retention, tamper resistance and access policies to be decided.

## Assumptions, open decisions and verification gates

- **INF-01:** Confirm single-node pilot versus three-manager production quorum and worker count; diagrams show options rather than purchased infrastructure.
- **INF-02:** Confirm Nginx-to-Swarm private connectivity (VPN, private VLAN or dedicated private network), routing endpoint and upstream mTLS feasibility.
- **INF-03:** Confirm Cloudflare TLS mode, origin authentication, proxy header allowlist and client-IP trust chain.
- **INF-04:** Confirm PostgreSQL topology, backup location, replication, encryption, RPO/RTO and service credential isolation.
- **INF-05:** Confirm broker technology and durable queue/outbox operational policy; Redis alone is not a guarantee of durable event delivery.
- **SEC-01:** Complete threat model (DOC-203) for each crossing; approve secrets management, identity issuer, service-to-service authentication and logging retention.
- **BIZ-01:** Finalize qualified-view rules and non-cash points calculation before awarding points.
- **OPS-01:** Validate firewall rules from the actual Nginx VM and all Swarm hosts, including published port exposure, node failover and rollback.
- **OPS-02:** Test restore, service degradation, queue replay, moderation takedown and ledger reversals.

## Release boundaries

R1 enables identity, profiles, creator content, streaming, moderation, verified engagement and non-cash points. R2 business verification/reviews, R3 ticketing/payment and R4 real-money settlement/payouts are **excluded** from live R1 topology and may only be added after separate design and security approvals.

## Review / sign-off

DOC-202 is submitted as a **full draft for review**. It does not authorize production deployment. Reviewer: __________  Date: __________  Decision: Approve / Changes required. Subsequent updates to approved DOC-201 must be separately controlled.