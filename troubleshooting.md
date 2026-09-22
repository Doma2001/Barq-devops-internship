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



