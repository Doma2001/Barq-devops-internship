# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## 01 / 22-09-2026 / 21:00
- Symptom:             app-01/app-02 are unhealthy when i used docker compose ps -a command
- Hypothesis:          problem in the healthcheck of the docker-compose file
- Command or test:     docker inspect
- Actual output:       http error 404 not found
- Failed attempt and what changed your thinking: none
- Root cause:          healthcheck was searching for \healthz (does not exist) not health
- Fix:                 changed the \healthz to \health in the docker compose file in the healthcheck part
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.


## 02 / 22-09-2026 / 21:00
- Symptom:             when i used curl -i  http://127.0.0.1:8080/ i got an error curl (56)
- Hypothesis:          the port was written wrong somewhere like nginx or the compose file
- Command or test:     compared the nginx.conf and the compose file
- Actual output:       curl (56) Recv failure: Connection reset by peer
- Failed attempt and what changed your thinking: 
- Root cause:          the compose file did have the wrong port 81 instead of 80
- Fix:                 changed the port 81 to 80 in the docker compose file in the NGINX part
- Retest evidence:
- Related commit:
- Remaining uncertainty:


## 03 / 22-09-2026 / 20:32
- Symptom: After fixing the port mapping, `curl http://127.0.0.1:8080/` returned `502 Bad Gateway`.
- Hypothesis: NGINX can reach the app-01 container over the network but not the Flask process itself — either wrong upstream port, or the app bound only to loopback.
- Command or test: `docker compose logs nginx --tail=30`; `grep -n "APP_PORT\|app.run" app/server.py`; `grep -n "app-01:" nginx/nginx.conf`; `docker compose exec app-01 printenv | grep APP_`; `docker compose exec nginx wget -qO- http://app-01:8080/health`
- Actual output: NGINX logs showed `connect() failed (111: Connection refused) ... upstream: "http://172.19.0.3:8081/"`. Flask listens on `APP_PORT` (default 8080), but nginx.conf's `upstream application_pool` pointed to `app-01:8081`. Also `APP_HOST` was `127.0.0.1` in docker-compose.yml, restricting the app to same-container connections only.
- Failed attempt and what changed your thinking: After only changing `APP_HOST` to `0.0.0.0` and rebuilding, still saw 502 — checked `printenv` inside app-01 to confirm the env var actually took effect (it had), which showed the remaining problem was the upstream port, not the bind address.
- Root cause: Two combined misconfigurations: (1) NGINX upstream block used port `8081` instead of `8080` for app-01, and (2) Flask app was bound to `127.0.0.1` instead of `0.0.0.0`, so it rejected connections from the separate NGINX container even on the same Docker network.
- Fix: Changed `app-01:8081` to `app-01:8080` in `nginx/nginx.conf`; changed `APP_HOST` from `127.0.0.1` to `0.0.0.0` in `docker-compose.yml`.
- Retest evidence: `docker compose exec nginx wget -qO- http://app-01:8080/health` returned valid JSON. `curl -i http://127.0.0.1:8080/` returned `200 OK` with expected JSON body and `X-Instance-ID: app-01` header.
- Related commit: fix: correct nginx upstream port and app bind address
- Remaining uncertainty: None.

## 04 / 22-09-2026 / 20:45
- Symptom: `curl /instance` always returned `"instance_id":"app-01"`, even when the request should have hit app-02.
- Hypothesis: app-02's INSTANCE_ID environment variable was misconfigured to the same value as app-01.
- Command or test: Inspected the `app-02` service block in `docker-compose.yml`.
- Actual output: `app-02` had `INSTANCE_ID: "app-01"` under its environment block instead of `"app-02"`.
- Failed attempt and what changed your thinking: N/A — root cause was visible directly in the compose file once compared line-by-line against app-01's block.
- Root cause: Copy-paste error in docker-compose.yml — app-02's environment override for INSTANCE_ID was never changed from app-01's value.
- Fix: Changed `INSTANCE_ID: "app-01"` to `INSTANCE_ID: "app-02"` in the app-02 service block, then ran `up -d --build --force-recreate` to force the env var to be re-injected (a plain restart does not re-read environment values).
- Retest evidence: Looping curl to `/instance` 8 times returned alternating "app-01"/"app-02" values, confirming both distinct instances are being load-balanced correctly.
- Related commit: fix: correct duplicate INSTANCE_ID for app-02
- Remaining uncertainty: One transient 502 appeared on the very first request right after --force-recreate, before containers reached "healthy" — expected startup behavior, not a bug.

## 05 / 22-09-2026 / 21:10
- Symptom: All requests to /records and POST /records returned {"error":"postgres_unavailable"}.
- Hypothesis: DATABASE_URL credentials or connection details don't match what PostgreSQL is actually configured with.
- Command or test: `docker compose exec app-01 printenv | grep DATABASE_URL`; `grep POSTGRES_ docker-compose.yml`; `cat config/app.env`; direct connection test with `python -c "import psycopg; psycopg.connect(...)"` inside app-01.
- Actual output: config/app.env had DATABASE_URL password ending in "d" and port 5433, while docker-compose.yml's POSTGRES_PASSWORD ended in "c" and postgres listens on its default port 5432.
- Failed attempt and what changed your thinking: First fix only corrected the password, left port as 5433 — still failed. Direct psycopg.connect() test with the corrected password AND port 5432 succeeded silently, isolating the port as the remaining issue.
- Root cause: config/app.env had two wrong values: a mistyped password (vK8d instead of vK8c) and a wrong PostgreSQL port (5433 instead of the actual 5432).
- Fix: Corrected DATABASE_URL in config/app.env to use password ending "c" and port 5432. (Also corrected REDIS_URL port from 6380 to the actual 6379.)
- Retest evidence: POST /records returned a new created record (id 3); GET /records returned existing seeded records plus the new one.
- Related commit: fix: correct DATABASE_URL password and port, REDIS_URL port in config/app.env
- Remaining uncertainty: One transient 502 occurred immediately after --force-recreate, before healthcheck passed — same expected startup-window behavior seen earlier, not a new bug.

## 06 / 22-09-2026 / 21:20
- Symptom: Records created via POST /records (e.g. id=3 "test record") disappeared after `docker compose restart postgres`, while the original seeded records (id=1, id=2) survived.
- Hypothesis: PostgreSQL's actual data directory is not backed by the persistent named volume.
- Command or test: Inspected the `postgres` service block in docker-compose.yml.
- Actual output: Found `volumes: [postgres-data:/var/lib/postgresql/backup]` and `tmpfs: [/var/lib/postgresql/data]`. PostgreSQL's real data directory (/var/lib/postgresql/data) was mounted as tmpfs (wiped on restart), while the persistent named volume was bound to an unused path (/backup).
- Failed attempt and what changed your thinking: N/A — misconfiguration was clear once the two mount paths were compared against PostgreSQL's actual default data directory.
- Root cause: The named volume `postgres-data` was mounted to `/var/lib/postgresql/backup` (a path PostgreSQL never writes to), while the real data directory `/var/lib/postgresql/data` was mounted as tmpfs, so all writes were lost on every restart.
- Fix: Removed the `tmpfs: [/var/lib/postgresql/data]` line and changed the named volume mount to `postgres-data:/var/lib/postgresql/data` in docker-compose.yml.
- Retest evidence: Created a record ("persistence test", id=3), restarted the postgres container, and GET /records still showed id=3 alongside the original seeded records.
- Related commit: fix: mount postgres-data volume to the correct PostgreSQL data directory
- Remaining uncertainty: One transient 502 on the first POST immediately after force-recreate — same known startup-window behavior as before.

## 07 / 22-09-2026 / 21:35
- Symptom: TASK.md security requirement says only NGINX should be published on the host (port 8080); docker-compose.yml also published PostgreSQL (15432) and Redis (16379) directly to the host.
- Hypothesis: These extra published ports unnecessarily expose the database and cache to anything on the host machine, bypassing NGINX entirely — a security misconfiguration, not a functional bug.
- Command or test: Reviewed the `ports:` entries under the postgres and redis services in docker-compose.yml against the requirement in assessment/TASK.md.
- Actual output: postgres had `ports: ["127.0.0.1:15432:5432"]` and redis had `ports: ["127.0.0.1:16379:6379"]`, both violating the "publish only NGINX" requirement.
- Failed attempt and what changed your thinking: N/A — this was a direct requirement check, not trial and error.
- Root cause: Unnecessary `ports:` mappings on postgres and redis services exposed them directly to the host, when internal Docker `networks` (not `ports`) is what actually enables app-01/app-02 to reach them by service name.
- Fix: Removed the `ports:` entries from both the postgres and redis service blocks in docker-compose.yml. Internal service-to-service communication continues to work via the shared `backend` network.
- Retest evidence: `docker compose ps -a` showed postgres and redis with no host port mappings (only nginx shows `127.0.0.1:8080->80/tcp`). GET /records and GET /counter both continued to work normally, confirming internal connectivity was unaffected.
- Related commit: fix: remove unnecessary host port exposure for postgres and redis
- Remaining uncertainty: None.
