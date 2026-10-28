# Staging — pending infrastructure ADRs

Dedicated Nginx VM outside Swarm. Only private, protected Nginx-to-Swarm routing.
No production or staging deployment manifests are enabled; host sizing, certificates,
networking, secret ownership, backups, and restore objectives remain to be resolved.
