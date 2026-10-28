# Infrastructure

Infrastructure configurations will support KoloVibe's private service network and dedicated reverse-proxy boundary.

The current architecture calls for a dedicated Nginx virtual machine outside the service cluster. Protected transport, certificate responsibility, host sizing, service discovery, network isolation, secrets management and recovery targets must be finalized before deployment manifests are introduced.

No live environment is configured by the files in this directory.
