# Security and production-readiness review

Record at least 8 concrete risks or improvements relevant to your final solution.
This is a review requirement, not the number of hidden faults.

For each finding:
- Risk and evidence:
- Impact:
- Implemented fix / commit:
- Production follow-up:
- How to verify:

Cover secrets, ports, container user, image selection, networks, persistence/backup,
logging/monitoring and availability. Separate completed work from planned improvements.

## Finding 1: Hardcoded database credentials, tracked in git history
- **Risk and evidence:** `POSTGRES_PASSWORD` was hardcoded in `docker-compose.yml`, and the same password embedded in `DATABASE_URL` inside `config/app.env`, which was tracked by git (`git ls-files` confirmed it). `git log --all -p` showed the plaintext password appearing in multiple past commits, including an earlier (incorrect) version of it.
- **Impact:** Anyone with read access to the repository (or its history) has the database credentials, even after they're removed from the current file.
- **Implemented fix / commit:** Removed `config/app.env` from git tracking (`git rm --cached`), added it to `.gitignore`, created `config/app.env.example` with placeholder values, and replaced the hardcoded `POSTGRES_PASSWORD` in `docker-compose.yml` with `${POSTGRES_PASSWORD}` sourced from an untracked root `.env` file. Commit: `security: stop tracking config/app.env, use env var for POSTGRES_PASSWORD`.
- **Production follow-up:** If this were a real production credential, it must be rotated immediately — removing it from files does not remove it from git history. A real deployment should use a secrets manager (e.g. Docker secrets, Vault) rather than env files at all.
- **How to verify:** `git ls-files | grep app.env` returns only `config/app.env.example` (confirmed). `GET /records` still returns data correctly after rebuild, confirming the app still reads credentials properly.


## Finding 2: PostgreSQL and Redis ports published directly to the host
- **Risk and evidence:** `docker-compose.yml` originally published `postgres` on `127.0.0.1:15432` and `redis` on `127.0.0.1:16379`, directly reachable from the host, bypassing NGINX entirely — contradicting the requirement that only NGINX be published.
- **Impact:** Any process on the host machine (or anything that gained host access) could connect straight to the database or cache without going through the application layer.
- **Implemented fix / commit:** Removed both `ports:` blocks; service-to-service communication continues via the Docker `networks` block (no host exposure needed for internal traffic). Commit: `fix: remove unnecessary host port exposure for postgres and redis`.
- **Production follow-up:** None needed beyond this fix; could additionally restrict the `backend` network further if more services are added later.
- **How to verify:** `docker compose ps -a` shows no host port mapping for postgres/redis (only nginx shows `127.0.0.1:8080->80/tcp`); `GET /records` and `GET /counter` still work, confirming internal connectivity is unaffected.

## Finding 3: PostgreSQL data directory mounted as tmpfs instead of persistent volume
- **Risk and evidence:** The named volume `postgres-data` was mounted at `/var/lib/postgresql/backup` (a path PostgreSQL never writes to), while the actual data directory `/var/lib/postgresql/data` was mounted as `tmpfs`, so every write was lost on restart.
- **Impact:** Total data loss on any container restart or recreation — unacceptable for any real database.
- **Implemented fix / commit:** Removed the `tmpfs` mount, changed the named volume target to `postgres-data:/var/lib/postgresql/data`. Commit: `fix: mount postgres-data volume to the correct PostgreSQL data directory`.
- **Production follow-up:** Add scheduled automated backups (see Finding 7) in addition to volume persistence, since a volume alone doesn't protect against disk failure or accidental `docker volume rm`.
- **How to verify:** Created a record, ran `docker compose restart postgres`, confirmed the record was still present in `GET /records` afterward.


## Finding 4: Application container runs as root despite a dedicated user being created
- **Risk and evidence:** The `Dockerfile` creates a non-root `app` user (`groupadd`/`useradd`, uid 10001) and even `COPY --chown=app:app`, but then explicitly sets `USER root` before the final `CMD`, so the Flask process actually runs as root inside the container.
- **Impact:** If the application process is ever compromised (e.g. a future dependency vulnerability), the attacker has root inside the container rather than a restricted user, increasing the blast radius of a container escape.
- **Implemented fix / commit:** Changed `USER root` to `USER app` in Dockerfile. Commit: `security: run app container as non-root user`.
- **Production follow-up:** Combine with a read-only root filesystem (`read_only: true` in compose) where possible for defense in depth.
- **How to verify:** `docker compose exec app-01 whoami` returns `app` (confirmed).

## Finding 5: NGINX failover configuration weakens availability during a backend outage
- **Risk and evidence:** `nginx.conf`'s upstream block uses `max_fails=0` (never marks a failing backend as down) combined with `proxy_next_upstream off` (never retries a failed request on the other backend).
- **Impact:** If one app instance goes down, a portion of requests routed to it will fail with 502 instead of silently failing over to the healthy instance — undermining the two-instance setup's purpose.
- **Implemented fix / commit:** Set `max_fails=3 fail_timeout=10s` on both upstream
  servers and changed `proxy_next_upstream` from `off` to
  `error timeout http_502 http_504` in nginx.conf. Commit:
  `fix: enable fast NGINX failover (max_fails, proxy_next_upstream)`.
- **Production follow-up:** Add active health-check-based upstream removal if using NGINX Plus, or an external load balancer with health checks.
- **How to verify:** With app-01 stopped, validate.py shows /ready, /records,
  and /counter all still PASS (confirmed) — only the "both backends serving
  traffic" check fails, as expected since one backend is intentionally down.
