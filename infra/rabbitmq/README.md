# RabbitMQ DHI deployment candidate — NOT ACTIVE

The broker is defined in the single [Swarm deployment YAML](../swarm/staging.yml);
there is no separate RabbitMQ stack. Its configuration stays in this directory.
The candidate has zero replicas and is not a running or accepted broker.
The approved architecture amendment uses RabbitMQ + Celery,
**not Redis**. Deploy only from VM1 manager after the prerequisites below are met.

- External overlay is the already-created encrypted, internal
  `kolovibe_messaging` network (172.28.11.0/24), whose encryption and full VCN
  non-overlap still require further evidence. No broker port is published.
- `RABBITMQ_DHI_IMAGE` must be a reviewed, immutable `dhi.io/rabbitmq@sha256:...`
  reference. Registry entitlements and read-only pull credentials must be checked.
- `RABBITMQ_MEMORY_LIMIT` is deliberately **required** and has no default.
  Both OCI VMs have ~956 MiB of RAM and existing workloads. Do **not** reuse
  the previous 1024M limit or invent a capacity figure. Budget RabbitMQ memory,
  Erlang overhead, OS, Docker, Django and Celery before enabling placement.
  API memory limits/reservations are also required in the single deployment file.
- Verify the manager-applied `node.labels.kolovibe.rabbitmq == true` placement
  selects a healthy node with durable storage; a named Docker local volume does
  not migrate with a Swarm task. Do not delete any existing worker volumes.
- Provision each external Swarm secret (TLS CA/cert/key, scoped definitions),
  validate SANs, TLS client permissions and definitions import. Rotate secrets
  with versioned replacements; do not place passwords in build layers.
- Confirm service producer/consumer access to the messaging overlay without
  joining unrelated workloads to the broker/data networks.
- Test durable queues, publisher confirms, deduplication, retries, dead letters,
  memory/disk alarms and recovery after task/node failure.
- Verify encrypted backups, monitoring, restoration and approval before rolling
  the single-replica broker into service.

The repository's static preflight tests are not an image pull, live network probe,
OPA authorization check, sizing test or a RabbitMQ deployment.
