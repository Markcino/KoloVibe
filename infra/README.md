# Infrastructure

Infrastructure configurations will support KoloVibe's private service network and dedicated reverse-proxy boundary.

The 2026-11-01 ADR-003 implementation amendment records Nginx installed as a host service on Oracle VM1 alongside the single Swarm manager, outside Swarm, with VM2 as worker. This supersedes the dedicated-third-VM assumption for the pilot and does not provide high availability. The owner reports Cloudflare Tunnel hostnames `api.cabetechs.shop` (API) and `kolovibe.cabetechs.shop` (application). Actual Tunnel ingress, Nginx virtual hosts, origin authentication, encrypted gateway transport, certificate responsibility, network isolation, secrets, capacity and recovery still require verification. RabbitMQ DHI with Celery is the broker; Redis is not the current KoloVibe broker.

No live environment is configured by the files in this directory.
