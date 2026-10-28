> Source: Stage2_Architecture_Change_Record_v0_3.docx (text export; original formatting, formulas and embedded images are not included). Original review status is retained.

<PARSED TEXT FOR PAGE: 1 / 1>
Stage 2 Architecture Change Record —
v0.3
Date: 28 October 2026 | Decision DEC-004 | Status: Approved placement; detailed topology under
review


Approved decision
Nginx will run on a dedicated server or virtual machine outside the Docker Swarm cluster.
Docker Swarm will host the Django microservices and background workers. Nginx will not be a
Swarm service.


Reference traffic flow
Flutter / Browser → Cloudflare (if enabled) → Nginx VM → private/VPN Swarm gateway →
Django web/API microservices → service-owned databases, workers and media provider.


Mandatory security controls
   No direct public access to Swarm ingress except via authorized proxy path.
   Authenticated encrypted connection from Nginx to Swarm; verify certificates.
   Harden and patch the Nginx VM independently; restrict SSH/admin access.
   Trust only controlled forwarding headers; verify Django ALLOWED_HOSTS and proxy
    settings.
   Restrict PostgreSQL, Redis, Docker API and internal metrics to private networks.
   Test proxy failover or document single-proxy pilot outage risk.


Open architecture decisions
Proxy VM sizing/OS, HA design, Swarm node count, private network method, database hosting,
Cloudflare usage and TLS certificate management remain subject to design review.


Review status
DEC-004 approved by product owner. Stage 2 overall remains in review; this record is not
evidence of deployment or penetration testing.