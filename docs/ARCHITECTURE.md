# Diagram notes

# Architecture

See `architecture.png` at the repository root for the full diagram.

## Summary
- **Public entry point:** NGINX only, published as `0.0.0.0:8090 -> 80` on the
  host. This is the sole point where anything outside the Docker network can
  reach the system.
- **frontend network:** Contains only NGINX (reachable from the host).
- **backend network (`internal: true`):** Contains app-01, app-02, app-03,
  PostgreSQL and Redis. This network has no route to the host at all — even
  if a `ports:` mapping were accidentally added back, `internal: true` blocks
  host access at the Docker network level as a second line of defense
  (belt-and-suspenders alongside the "no ports:" fix in security_review.md
  Finding 2).
- **Request flow:** Client -> NGINX:8090 -> round-robin across app-01/02/03
  on :8080 each -> PostgreSQL (via DATABASE_URL) and/or Redis (via REDIS_URL)
  depending on the endpoint.
- **Persistence:** Only PostgreSQL data persists (named volume `postgres-data`
  mounted at PostgreSQL's real data directory). Redis is treated as a
  non-persistent cache/counter store — losing it loses the counter value but
  not core application data.
- **Health/readiness:**
  - `/health` — process is alive (no dependency checks)
  - `/ready` — PostgreSQL and Redis are both reachable
  - `/instance` — returns `X-Instance-ID`, used to prove NGINX is actually
    load-balancing across all instances rather than pinning to one

## Remaining single points of failure
- **NGINX itself** — only one instance; if it goes down, the whole system is
  unreachable from outside. A production setup would put a redundant
  load balancer or multiple NGINX replicas in front.
- **PostgreSQL** — only one instance, no replica/standby. `backup.sh`/
  `restore.sh` protect against data loss, but not against downtime during
  a PostgreSQL outage.
- **Redis** — only one instance, no persistence configured. Acceptable here
  since Redis is used as a cache/counter, not a source of truth, but this
  should be re-evaluated if Redis usage grows to hold anything critical.
