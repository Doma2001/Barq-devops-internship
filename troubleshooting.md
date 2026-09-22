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
