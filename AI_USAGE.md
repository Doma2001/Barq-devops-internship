# AI usage disclosure
# AI Usage Disclosure

AI assistance (Claude, via chat) was used throughout this assessment as a
debugging/pairing partner. In every case, I ran the actual commands on my own
machine, read the real output, and verified the result myself before moving on
or committing — the AI never had direct access to my running environment.

## Tool
Claude (Anthropic), conversational chat interface.

## Purpose and usage pattern
Used as an interactive troubleshooting and learning aid: I described symptoms
or pasted real command output, the AI suggested specific diagnostic commands
or explained a concept, and I ran everything myself and reported back the
actual results before we drew any conclusion. For scripts (validate.py,
failure_test.py, backup.sh, restore.sh, ci.yml), the AI proposed a full
structure with inline explanations, which I then ran and adjusted based on
real failures (e.g. the CI env-file issue, the nginx failover 504s).

## Affected files and what AI helped with

| File(s) | What AI helped with | How I verified it |
|---|---|---|
| docker-compose.yml, nginx/nginx.conf, Dockerfile | Diagnosing each broken-environment issue (healthcheck path, port mismatch, upstream port/bind address, duplicate INSTANCE_ID, tmpfs vs volume, exposed ports, root user, failover config) by reasoning through my real `docker inspect`/`logs`/`curl` output | I ran every command myself; each fix was only accepted after I re-ran the relevant test and saw the real before/after difference (e.g. ps -a status, curl status codes) |
| config/app.env, .env, .gitignore | Identifying leaked secrets in git history and proposing the untrack + env-var approach | Confirmed with `git ls-files`, `git log --all -p`, and a working `GET /records` after the change |
| troubleshooting.md, log_analysis.md, security_review.md | Drafting entries in the required template based on the real evidence I had just produced | I only accepted entries describing tests I had actually run and outputs I had actually pasted; I did not let unconfirmed items be marked "implemented" |
| scripts/analyze_access.py (log analysis) | Explaining the JSON-lines parsing approach, dedup logic, and percentile method step by step; I wrote/ran each increment myself | Independently cross-checked several results (status counts, error breakdown, retry counts) — all matched between my run and the explanation given |
| validate.py, failure_test.py | Full script structure with explained design choices (bounded timeouts, try/finally cleanup, PASS/FAIL per check) | Ran both scripts myself against the real environment, including intentionally breaking it (stopping app-01) to confirm they detect real failure, not just report success blindly |
| backup.sh, restore.sh | Script structure using pg_dump/psql via docker compose exec | Tested end-to-end against actual data loss: created a marker record, backed up, destroyed the postgres volume with `down -v`, restored, and confirmed the marker record came back |
| .github/workflows/ci.yml | Initial workflow structure; iterating on real CI failures (missing env files, insufficient readiness check) | Confirmed via actual GitHub Actions runs — CI #1–#3 failed with real errors I diagnosed and fixed one at a time, CI #4 passed (screenshot taken from the Actions tab) |

## What I did NOT rely on AI for
- I did not copy any output or conclusion I hadn't personally reproduced and
  verified first. Every "PASS"/fix documented in troubleshooting.md and
  security_review.md corresponds to a real command I ran and a real result I
  pasted back, not an assumption.
- No secrets, real credentials, or production data were involved — only the
  synthetic lab credentials provided with the assessment.
