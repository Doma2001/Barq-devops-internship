# Technical decisions
# Decisions, Assumptions, Alternatives and Trade-offs

## Decision 1: Error rate defined as status >= 500 only (excludes 404)
- **Decision:** In log_analysis.md, the "error rate" metric counts only 5xx
  responses, not 404s.
- **Assumption:** A 404 means a client requested a path that legitimately
  doesn't exist — that's expected traffic behavior, not a server failure.
- **Alternative considered:** Count 4xx + 5xx together as "errors". Rejected
  because it would conflate client mistakes with actual system health problems,
  making the error-rate metric less useful for on-call decision-making.
- **Trade-off / limitation:** If a 404 spike is itself the symptom of a real
  bug (e.g. a broken route after a deploy), this metric would miss it — a
  separate "404 rate by path" check would be needed to catch that case.

## Decision 2: NGINX upstream max_fails=3 / fail_timeout=10s (not 0, not 10)
- **Decision:** Set max_fails=3 with fail_timeout=10s instead of leaving the
  original max_fails=0, or over-correcting to something like max_fails=10.
- **Assumption:** 3 consecutive failures is enough to confidently say a
  backend is actually down, without reacting to one transient blip.
- **Alternative considered:** max_fails=10 — rejected because validate.py
  showed it let 504s reach the client for too long before failover kicked in
  (real evidence: /ready returned 504 while app-01 was down, before this fix).
- **Trade-off / limitation:** A genuinely flaky (not fully down) backend could
  still get marked unavailable after only 3 transient errors, briefly reducing
  capacity to one instance until fail_timeout expires.

## Decision 3: PostgreSQL and Redis kept off host-published ports entirely
- **Decision:** Removed the `ports:` mappings for postgres and redis rather
  than restricting them to a firewalled range or leaving them open for debugging.
- **Assumption:** Nothing outside the Docker network legitimately needs direct
  access to these services — the app is the only intended client, and NGINX
  is the only intended public entry point (this is also an explicit TASK.md requirement).
- **Alternative considered:** Keep them bound to 127.0.0.1 only (as they
  originally were) for local debugging convenience. Rejected because the task
  explicitly requires only NGINX to be published, and internal `docker exec`
  is sufficient for debugging without any host exposure.
- **Trade-off / limitation:** Debugging postgres/redis directly now requires
  `docker compose exec` instead of a local GUI client connecting to
  127.0.0.1:5432 — slightly less convenient locally, but correct for the
  security requirement.

## Decision 4: Deduplicate log records by request_id, keep first occurrence
- **Decision:** In log_analysis.md and analyze_access.py, exact-duplicate log
  lines (same request_id) are deduplicated by keeping only the first
  occurrence before computing any statistic.
- **Assumption:** The 5 duplicate pairs found were a logging artifact (proven
  by byte-for-byte identical timestamps and request_time — a real retry would
  show a different timestamp), not two separate real requests.
- **Alternative considered:** Keep all lines and divide relevant counts by 2
  for the affected IDs. Rejected as more error-prone and harder to justify
  than a straightforward "first occurrence wins" dedup with a set.
- **Trade-off / limitation:** This approach assumes ALL duplicates in this
  dataset follow the same pattern; it would silently mis-handle a case where a
  duplicate request_id legitimately represented two different requests (not
  observed here, but worth flagging as an assumption).

## Decision 5: backup.sh/restore.sh use plain SQL (pg_dump default format), not custom/compressed format
- **Decision:** pg_dump without `-Fc` (custom format), producing a plain
  `.sql` file.
- **Assumption:** For this assessment's scale (a handful of rows), backup
  size and restore speed are not a concern; readability/diffability of the
  backup file matters more for review purposes.
- **Alternative considered:** `pg_dump -Fc` (compressed custom format, usable
  with `pg_restore -j` for parallel restore). Rejected for this exercise as
  unnecessary complexity — would be the right choice for a production
  database of real size.
- **Trade-off / limitation:** Plain SQL dumps don't scale well to large
  databases (slow, large files, no parallel restore) — this decision would
  need revisiting before production use.

## Decision 6: CI secrets injected via GitHub Actions repository secrets, not committed defaults
- **Decision:** POSTGRES_PASSWORD is read from a GitHub Actions secret and
  written into .env/config/app.env at CI runtime, rather than committing a
  fixed "test" password anywhere in the repo (including ci.yml itself).
- **Assumption:** Even a "fake" lab password shouldn't be committed in
  plaintext, since it reinforces the same bad habit that caused the original
  secrets-in-git-history problem (Finding 1 in security_review.md).
- **Alternative considered:** Commit a hardcoded non-sensitive placeholder
  password directly in ci.yml for simplicity. Rejected because it would
  contradict the fix already made for Finding 1 and set a bad precedent even
  in a lab context.
- **Trade-off / limitation:** Anyone forking this repo must manually add the
  same repository secret before CI will pass — slightly more setup friction
  than a self-contained hardcoded value.
